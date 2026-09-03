"""Compute swing metrics for a session (Phase 5 dev entrypoint).

    python -m golf_sim.analysis.cli <session_dir>|--latest

Reads the filtered TRC from the session's pose-3d output (falling back to
the unfiltered one) and writes metrics.json into the session folder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from golf_sim.analysis.ball_detect import (
    detect_impact_by_disappearance,
    find_ball_address_frame,
    find_ball_at_address,
)
from golf_sim.analysis.ideal_pose import build_all_ideal_frames
from golf_sim.analysis.metrics import compute_metrics
from golf_sim.analysis.p_positions import detect_p_positions
from golf_sim.analysis.phases import PhaseDetectionError, SwingPhases, detect_phases
from golf_sim.analysis.quality import assess_tracking_quality
from golf_sim.analysis.tips import generate_tips, tips_to_dicts
from golf_sim.config import Club, load_config, resolve_state_path
from golf_sim.trc import read_trc


def _p_positions_payload(seq, report, config, club: Club | None = None) -> list[dict]:
    handedness = config.analysis.golfer_handedness
    positions = detect_p_positions(seq, report.phases, handedness=handedness)
    frame_by_name = {p.name: p.frame_index for p in positions}
    ideal_frames = build_all_ideal_frames(
        seq, report.phases, frame_by_name, config.metrics, handedness=handedness, club=club
    )
    return [
        {
            "name": p.name,
            "label": p.label,
            "frame_index": p.frame_index,
            "time_s": round(p.time_s, 4),
            "ideal_frame": {
                marker: [round(float(c), 4) for c in xyz]
                for marker, xyz in ideal_frames[p.name].items()
            },
        }
        for p in positions
    ]


def _camera_json_dir(session_dir: Path, camera_role: str) -> Path:
    return session_dir / "pose2sim" / "pose" / f"{camera_role}_json"


# HALPE_26 keypoint indices (Pose2Sim's default pose model).
_LWRIST, _RWRIST = 9, 10
_LANKLE, _RANKLE = 15, 16


def _load_keypoints(session_dir: Path, camera_role: str, frame_index: int) -> np.ndarray | None:
    pose_path = _camera_json_dir(session_dir, camera_role) / f"{camera_role}_{frame_index:06d}.json"
    if not pose_path.exists():
        return None
    try:
        raw = json.loads(pose_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    people = raw.get("people") or []
    if not people:
        return None
    keypoints = np.asarray(people[0].get("pose_keypoints_2d", []), dtype=float).reshape(-1, 3)
    if keypoints.shape[0] < 26:
        return None
    return keypoints


def _mean_valid_point(keypoints: np.ndarray, indices: list[int]) -> tuple[float, float] | None:
    points = keypoints[indices, :2]
    confidences = keypoints[indices, 2]
    valid = np.isfinite(confidences) & (confidences > 0)
    if not valid.any():
        return None
    x, y = np.mean(points[valid], axis=0)
    if not np.isfinite(x) or not np.isfinite(y):
        return None
    return float(x), float(y)


def _pose_anchor_from_pose(
    session_dir: Path, camera_role: str, frame_index: int, anchor: str
) -> tuple[float, float] | None:
    keypoints = _load_keypoints(session_dir, camera_role, frame_index)
    if keypoints is None:
        return None
    # In the face-on view the ball sits below the golfer's feet and between the
    # legs, so anchor on the ankle midpoint. Only the wrist mode uses the hands.
    if anchor == "wrists":
        return _mean_valid_point(keypoints, [_LWRIST, _RWRIST])
    return _mean_valid_point(keypoints, [_LANKLE, _RANKLE])


def _ball_roi_offsets_from_pose(
    session_dir: Path,
    camera_role: str,
    frame_index: int,
    anchor: str,
    default_offsets: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    if anchor not in ("legs", "feet"):
        return default_offsets
    keypoints = _load_keypoints(session_dir, camera_role, frame_index)
    if keypoints is None:
        return default_offsets
    ankles = keypoints[[_LANKLE, _RANKLE], :2]
    confidences = keypoints[[_LANKLE, _RANKLE], 2]
    valid = np.isfinite(confidences) & (confidences > 0)
    if valid.sum() < 2:
        return default_offsets
    # Horizontal band = between the ankles (with margin); vertical band starts
    # just below the ankles and extends down toward the mat, where the ball
    # rests below the feet.
    span = float(abs(ankles[0, 0] - ankles[1, 0]))
    half_width = int(max(70, min(140, span * 0.75)))
    return (-half_width, half_width, 10, 240)


def _video_frame(video_path: Path, frame_index: int) -> np.ndarray | None:
    capture = cv2.VideoCapture(str(video_path))
    try:
        if not capture.isOpened():
            return None
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()


def pick_trc(session_dir: Path) -> Path:
    pose3d = session_dir / "pose2sim" / "pose-3d"
    filtered = sorted(pose3d.glob("*_filt_*.trc"))
    if filtered:
        return filtered[-1]
    unfiltered = sorted(pose3d.glob("*.trc"))
    if unfiltered:
        return unfiltered[-1]
    raise FileNotFoundError(
        f"no .trc under {pose3d} -- run `python -m golf_sim.pose.cli full` first"
    )


def analyze_session(session_dir: Path, config) -> Path:
    trc_path = pick_trc(session_dir)
    seq = read_trc(trc_path)

    # The audio trigger fires at impact, so the saved clip places impact at
    # pre_capture_delay_s into it -- hand this to phase detection as the
    # impact anchor (see detect_phases). Falls back to geometry if metadata
    # is missing (e.g. a manually assembled clip).
    phases = None
    ball_info = {
        "detected": False,
        "address_xy": None,
        "radius": None,
        "impact_frame": None,
        "impact_source": "estimated",
    }
    club: Club | None = None
    meta_path = session_dir / "metadata.json"
    if meta_path.exists():
        try:
            metadata = json.loads(meta_path.read_text())
            delay = metadata.get("pre_capture_delay_s")
            club = metadata.get("club")
            if delay is not None:
                phases = detect_phases(seq, impact_hint_frame=round(float(delay) * seq.fps))
        except (json.JSONDecodeError, OSError, ValueError):
            phases = None

    if phases is not None:
        camera_role = config.ball.detection_camera_role
        video_path = session_dir / f"{camera_role}.mp4"
        address_frame = phases.address_frame
        anchor_xy = _pose_anchor_from_pose(
            session_dir, camera_role, address_frame, config.ball.detection_anchor
        )
        roi_offsets = _ball_roi_offsets_from_pose(
            session_dir,
            camera_role,
            address_frame,
            config.ball.detection_anchor,
            (
                config.ball.roi.x_min_offset,
                config.ball.roi.x_max_offset,
                config.ball.roi.y_min_offset,
                config.ball.roi.y_max_offset,
            ),
        )
        frame = _video_frame(video_path, address_frame)
        if anchor_xy is not None and frame is not None:
            ball = find_ball_at_address(
                frame,
                anchor_xy,
                (config.ball.hue_min, config.ball.hue_max),
                roi_offsets=roi_offsets,
                min_saturation=config.ball.min_saturation,
                min_value=config.ball.min_value,
                min_circularity=config.ball.min_circularity,
                min_area_px=config.ball.min_area_px,
            )
            if ball is not None:
                ball_xy = (float(ball[0]), float(ball[1]))
                ball_radius = float(ball[2])
                refined_address = find_ball_address_frame(
                    video_path,
                    ball_xy,
                    ball_radius,
                    address_frame,
                    hue_range=(config.ball.hue_min, config.ball.hue_max),
                    min_saturation=config.ball.min_saturation,
                    min_value=config.ball.min_value,
                    present_min_fraction=config.ball.present_min_fraction,
                )
                impact_frame = detect_impact_by_disappearance(
                    video_path,
                    ball_xy,
                    refined_address,
                    seq.fps,
                    radius=ball_radius,
                    hue_range=(config.ball.hue_min, config.ball.hue_max),
                    min_saturation=config.ball.min_saturation,
                    min_value=config.ball.min_value,
                    present_min_fraction=config.ball.present_min_fraction,
                    confirm_frames=config.ball.disappearance_confirm_frames,
                )
                if impact_frame is not None:
                    try:
                        refined = detect_phases(seq, impact_hint_frame=impact_frame)
                    except PhaseDetectionError:
                        refined = phases
                    phases = SwingPhases(
                        address_frame=refined_address,
                        top_frame=refined.top_frame,
                        impact_frame=impact_frame,
                    )
                    ball_info.update(
                        {
                            "detected": True,
                            "source_camera": camera_role,
                            "address_xy": [round(ball_xy[0], 2), round(ball_xy[1], 2)],
                            "radius": round(ball_radius, 2),
                            "impact_frame": impact_frame,
                            "impact_source": "ball",
                        }
                    )
                else:
                    ball_info.update(
                        {
                            "detected": True,
                            "source_camera": camera_role,
                            "address_xy": [round(ball_xy[0], 2), round(ball_xy[1], 2)],
                            "radius": round(ball_radius, 2),
                        }
                    )

    report = compute_metrics(
        seq, config.metrics, phases=phases, handedness=config.analysis.golfer_handedness
    )

    report = compute_metrics(
        seq,
        config.metrics,
        phases=phases,
        handedness=config.analysis.golfer_handedness,
        club=club,
    )

    out_path = session_dir / "metrics.json"
    payload = {
        "source_trc": trc_path.name,
        "club": club,
        "club_profile": config.metrics.club_profile_mapping.get(club) if club else None,
        # quality first so the UI can caveat everything below it when the
        # reconstruction is too poor to trust (see analysis.quality)
        "tracking_quality": assess_tracking_quality(seq).to_dict(),
        **report.to_dict(),
        "tips": tips_to_dicts(tips),
        "ball": ball_info,
        "p_positions": _p_positions_payload(seq, report, config, club=club),
    }
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", nargs="?", type=Path)
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    config = load_config()
    if args.latest:
        sessions = sorted((resolve_state_path(config.storage.data_dir) / "sessions").iterdir())
        session_dir = sessions[-1]
    elif args.session_dir is not None:
        session_dir = args.session_dir
    else:
        raise SystemExit("pass a session_dir or --latest")

    out_path = analyze_session(session_dir, config)
    print(f"metrics written to {out_path}\n")
    report = json.loads(out_path.read_text())
    phases = report["phases"]
    print(
        f"phases: address={phases['address_frame']} top={phases['top_frame']} "
        f"impact={phases['impact_frame']}"
    )
    for metric in report["metrics"]:
        flag = (
            ""
            if metric["in_range"] is None
            else ("  OK" if metric["in_range"] else "  ** OUT OF RANGE **")
        )
        print(f"  {metric['name']}: {metric['value']} {metric['unit']}{flag}")

    print("\nP-positions:")
    for pos in report["p_positions"]:
        print(f"  {pos['name']} ({pos['label']}): frame {pos['frame_index']}, {pos['time_s']}s")

    if report["tips"]:
        print("\ntips:")
        for i, tip in enumerate(report["tips"], 1):
            print(f"  {i}. [{tip['metric']} {tip['direction']}] {tip['text']}")
    else:
        print("\nno tips -- everything in range. Nice swing.")


if __name__ == "__main__":
    main()
