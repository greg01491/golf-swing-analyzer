"""Compute swing metrics for a session (Phase 5 dev entrypoint).

    python -m golf_sim.analysis.cli <session_dir>|--latest

Reads the filtered TRC from the session's pose-3d output (falling back to
the unfiltered one) and writes metrics.json into the session folder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from golf_sim.analysis.ball_detect import (
    detect_impact_by_disappearance,
    find_ball_address_frame,
    find_ball_at_address,
)
from golf_sim.analysis.frame_of_reference import AnalysisReference, infer_reference
from golf_sim.analysis.ideal_pose import build_all_ideal_frames
from golf_sim.analysis.metrics import compute_metrics
from golf_sim.analysis.p_positions import detect_p_positions
from golf_sim.analysis.phases import PhaseDetectionError, SwingPhases, detect_phases
from golf_sim.analysis.quality import assess_tracking_quality
from golf_sim.analysis.tips import generate_tips, tips_to_dicts
from golf_sim.config import Club, load_config, resolve_state_path
from golf_sim.pose.reconstruction_evidence import (
    review_camera_tolerances,
    verified_artifact_evidence,
)
from golf_sim.trc import read_trc


def _p_positions_payload(seq, report, config, club: Club | None = None) -> list[dict]:
    handedness = config.analysis.golfer_handedness
    reference = AnalysisReference(**report.reference_frame)
    positions = detect_p_positions(seq, report.phases, handedness=handedness, reference=reference)
    frame_by_name = {p.name: p.frame_index for p in positions}
    ideal_frames = build_all_ideal_frames(
        seq,
        report.phases,
        frame_by_name,
        config.metrics,
        handedness=handedness,
        club=club,
        reference=reference,
    )
    return [
        {
            "name": p.name,
            "label": p.label,
            "frame_index": p.frame_index,
            "time_s": round(p.time_s, 4),
            "available": p.available,
            "detected": p.detected,
            "estimate_reason": p.estimate_reason,
            "unavailable_reason": p.unavailable_reason,
            "ideal_frame": {
                marker: [round(float(c), 4) for c in xyz]
                for marker, xyz in ideal_frames[p.name].items()
                if np.isfinite(xyz).all()
            },
        }
        for p in positions
    ]


def _camera_json_dir(session_dir: Path, camera_role: str) -> Path:
    project = session_dir / "pose2sim"
    associated = project / "pose-associated" / f"{camera_role}_json"
    return associated if associated.is_dir() else project / "pose" / f"{camera_role}_json"


# HALPE_26 keypoint indices (Pose2Sim's default pose model).
_LWRIST, _RWRIST = 9, 10
_LANKLE, _RANKLE = 15, 16
_MARKER_INDICES = {
    "LShoulder": 5,
    "RShoulder": 6,
    "LElbow": 7,
    "RElbow": 8,
    "LWrist": 9,
    "RWrist": 10,
    "LHip": 11,
    "RHip": 12,
    "LKnee": 13,
    "RKnee": 14,
    "LAnkle": 15,
    "RAnkle": 16,
    "Head": 17,
    "Neck": 18,
    "Hip": 19,
}


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
    try:
        keypoints = np.asarray(people[0].get("pose_keypoints_2d", []), dtype=float).reshape(-1, 3)
    except (ValueError, TypeError):
        return None
    if keypoints.shape[0] < 26:
        return None
    return keypoints


def _reference_for_session(
    seq, metadata: dict, trc_path: Path, handedness: str
) -> AnalysisReference:
    try:
        artifact = verified_artifact_evidence(trc_path)
    except (OSError, ValueError, KeyError):
        artifact = None
    evidence = None if artifact is None else artifact.get("analysis_reference")
    if isinstance(evidence, dict):
        fingerprint = hashlib.sha256(trc_path.read_bytes()).hexdigest()
        if (
            evidence.get("source") == "calibrated_ground"
            and evidence.get("validated") is True
            and evidence.get("source_trc_sha256") == fingerprint
        ):
            try:
                return AnalysisReference(
                    up=evidence.get("up"),
                    target=evidence.get("target"),
                    ball=evidence.get("ball"),
                    source=f"calibrated_ground:{fingerprint}",
                )
            except (ValueError, TypeError):
                pass
    reference = infer_reference(seq, handedness)
    if evidence is not None:
        reference.reasons.append(
            "unmatched_reference: ground evidence did not validate against this TRC"
        )
    return reference


def _marker_observation_support(seq, session_dir: Path, camera_roles: list[str], config):
    if len(camera_roles) < 2:
        return None
    observations = {}
    for role in camera_roles:
        frames = np.full((seq.n_frames, 26, 3), np.nan)
        for frame in range(seq.n_frames):
            keypoints = _load_keypoints(session_dir, role, frame)
            if keypoints is not None:
                frames[frame] = keypoints[:26]
        observations[role] = frames
    support = {}
    half = max(1, round(config.turn_filter_window_s * seq.fps / 2))
    for name, index in _MARKER_INDICES.items():
        if not seq.has_marker(name):
            continue
        accepted = np.ones(seq.n_frames, dtype=bool)
        trajectory = seq.marker(name)
        for frames in observations.values():
            points = frames[:, index]
            camera_valid = np.isfinite(points).all(axis=1) & (points[:, 2] >= 0.3)
            for frame in range(seq.n_frames):
                start, end = max(0, frame - half), min(seq.n_frames, frame + half + 1)
                spatial = trajectory[start:end]
                if not np.isfinite(spatial).all():
                    continue
                held = np.linalg.norm(np.ptp(spatial, axis=0)) <= config.frozen_tolerance_m
                image = points[start:end, :2][camera_valid[start:end]]
                if (
                    held
                    and image.size
                    and np.linalg.norm(np.ptp(image, axis=0)) > config.held_observation_motion_px
                ):
                    camera_valid[frame] = False
            accepted &= camera_valid
        support[name] = accepted
    return support


def _wrist_visibility_by_camera(
    session_dir: Path,
    camera_roles: list[str],
    swing_start: int,
    swing_end: int,
    confidence_threshold: float = 0.6,
) -> dict[str, dict[str, float]] | None:
    start, end = max(0, min(swing_start, swing_end)), max(swing_start, swing_end)
    frame_count = end - start + 1
    if frame_count <= 0:
        return None

    if not any(any(_camera_json_dir(session_dir, role).glob("*.json")) for role in camera_roles):
        return None

    visibility: dict[str, dict[str, float]] = {}
    for role in camera_roles:
        visible = {_LWRIST: 0, _RWRIST: 0}
        for frame_index in range(start, end + 1):
            keypoints = _load_keypoints(session_dir, role, frame_index)
            if keypoints is None:
                continue
            confidence = keypoints[[_LWRIST, _RWRIST], 2]
            for index, score in zip((_LWRIST, _RWRIST), confidence, strict=True):
                visible[index] += int(np.isfinite(score) and score >= confidence_threshold)
        visibility[role] = {
            "LWrist": visible[_LWRIST] / frame_count,
            "RWrist": visible[_RWRIST] / frame_count,
        }
    return visibility


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


def apply_review_exclusions(seq, marker_support, camera_frame_rates, exclusions):
    """Mask selected 3D marker samples in a copy for diagnostic what-if metrics.

    A 2D observation exclusion cannot recover a replacement 3D point without
    retriangulation. Masking the corresponding saved 3D sample is deliberately
    conservative and leaves the source sequence and support evidence intact.
    """
    from golf_sim.trc import LandmarkSequence

    coords = seq.coords.copy()
    support = (
        None
        if marker_support is None
        else {
            name: np.asarray(values, dtype=bool).copy() for name, values in marker_support.items()
        }
    )
    applied = []
    for exclusion in exclusions:
        camera = exclusion["camera"]
        marker_name = exclusion["marker"]
        frame_index = int(exclusion["frame_index"])
        fps = camera_frame_rates.get(camera)
        if fps is None or not np.isfinite(fps) or fps <= 0:
            raise ValueError(f"no valid frame rate for {camera}")
        if not seq.has_marker(marker_name):
            raise ValueError(f"unknown 3D marker: {marker_name}")
        if frame_index < 0:
            raise ValueError("frame index must be nonnegative")

        observation_time = frame_index / fps
        if observation_time < seq.times[0] or observation_time > seq.times[-1]:
            raise ValueError(f"{camera} frame {frame_index} is outside the saved 3D sequence")
        trc_frame = int(np.argmin(np.abs(seq.times - observation_time)))
        marker_index = seq.marker_names.index(marker_name)
        coords[trc_frame, marker_index] = np.nan
        if support is not None and marker_name in support:
            if support[marker_name].shape != (seq.n_frames,):
                raise ValueError(f"invalid support length for {marker_name}")
            support[marker_name][trc_frame] = False
        applied.append(
            {
                "camera": camera,
                "frame_index": frame_index,
                "marker": marker_name,
                "trc_frame_index": trc_frame,
                "trc_time_s": float(seq.times[trc_frame]),
            }
        )

    return LandmarkSequence(seq.marker_names.copy(), seq.times.copy(), coords), support, applied


def analyze_session_what_if(session_dir: Path, config, exclusions: list[dict]) -> dict:
    """Recompute metrics in memory with reviewed marker observations excluded."""
    trc_path = pick_trc(session_dir)
    metrics_path = Path(session_dir) / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError("original metrics are unavailable for comparison")
    original = json.loads(metrics_path.read_text())
    saved_phases = original.get("phases")
    if not isinstance(saved_phases, dict):
        raise ValueError("original phase anchors are unavailable")

    seq = read_trc(trc_path)
    metadata_path = Path(session_dir) / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    camera_devices = getattr(getattr(config, "cameras", None), "devices", [])
    camera_roles = [device.role for device in camera_devices]
    camera_frame_rates = {
        role: metadata.get("cameras", {}).get(role, {}).get("fps")
        or next((device.fps for device in camera_devices if device.role == role), None)
        for role in camera_roles
    }
    reference = _reference_for_session(seq, metadata, trc_path, config.analysis.golfer_handedness)
    marker_support = _marker_observation_support(seq, session_dir, camera_roles, config.metrics)
    try:
        artifact = verified_artifact_evidence(trc_path)
    except (OSError, ValueError, KeyError):
        artifact = None
    if artifact is not None:
        reconstructed = {
            name: np.asarray(values, dtype=bool)
            for name, values in artifact.get("marker_support", {}).items()
        }
        if marker_support is None:
            marker_support = reconstructed
        else:
            for name, values in reconstructed.items():
                if name in marker_support and values.shape == marker_support[name].shape:
                    marker_support[name] &= values

    diagnostic_seq, diagnostic_support, applied = apply_review_exclusions(
        seq, marker_support, camera_frame_rates, exclusions
    )
    phases = SwingPhases(
        address_frame=int(saved_phases["address_frame"]),
        top_frame=int(saved_phases["top_frame"]),
        impact_frame=int(saved_phases["impact_frame"]),
        status=saved_phases.get("status", "valid"),
    )
    report = compute_metrics(
        diagnostic_seq,
        config.metrics,
        phases=phases,
        handedness=config.analysis.golfer_handedness,
        club=original.get("club") or metadata.get("club"),
        reference=reference,
        marker_support=diagnostic_support,
    )
    return {
        **report.to_dict(),
        "tips": tips_to_dicts(generate_tips(report)),
        "diagnostic_only": True,
        "warning": (
            "This what-if masks selected saved 3D marker samples. It does not retriangulate, "
            "repair missing geometry, or replace the original analysis."
        ),
        "exclusions": applied,
    }


def session_review_issues(session_dir: Path, config) -> dict:
    """Inspect metric dependencies in memory without changing saved analysis or reviews."""
    session_dir = Path(session_dir)
    original = json.loads((session_dir / "metrics.json").read_text())
    trc_path = pick_trc(session_dir)
    if original.get("source_trc") not in (None, trc_path.name):
        raise ValueError(
            "saved metrics refer to a different 3D artifact; explicit reanalysis required"
        )
    diagnostic = analyze_session_what_if(session_dir, config, [])
    seq = read_trc(trc_path)
    metadata = json.loads((session_dir / "metadata.json").read_text())
    cameras = metadata.get("cameras", {})
    roles = sorted(set(cameras) | {path.stem for path in session_dir.glob("camera_*.mp4")})
    roles = [role for role in roles if role in {"camera_1", "camera_2"}]
    issues = []
    blockers = []
    for metric in diagnostic["metrics"]:
        if metric["status"] == "valid":
            continue
        spans = metric.get("review_issues", [])
        for span in spans:
            times = seq.times[span["start_frame"] : span["end_frame"] + 1]
            for role in (roles if span["marker"] else []) or [None]:
                fps = cameras.get(role, {}).get("fps")
                mapped = (
                    isinstance(fps, (int, float))
                    and np.isfinite(fps)
                    and fps > 0
                    and np.isfinite(times).all()
                    and (times >= 0).all()
                    and (np.diff(times) > 0).all()
                )
                frames = (
                    sorted({round(float(timestamp) * fps) for timestamp in times}) if mapped else []
                )
                issues.append(
                    {
                        "metric": metric["name"],
                        "marker": span["marker"],
                        "camera": role,
                        "frame_indices": frames,
                        "fps": fps if mapped else None,
                        "start_time_s": span["start_time_s"],
                        "end_time_s": span["end_time_s"],
                        "reason": span["reason"],
                        "camera_attribution": "not_isolated",
                        "mapping_reason": (
                            None if mapped else "Saved camera frame mapping unavailable"
                        ),
                    }
                )
        reasons = [
            reason
            for reason in metric["reasons"]
            if not spans
            or not reason.startswith(
                (
                    "unverified_marker:",
                    "invalid_support:",
                    "insufficient_coverage:",
                    "unsupported_geometry:",
                )
            )
        ]
        if reasons:
            blockers.append({"metric": metric["name"], "reasons": reasons})
    try:
        tolerances = review_camera_tolerances(trc_path, config, issues)
    except (OSError, ValueError, KeyError, TypeError, cv2.error) as exc:
        tolerances = {"available": False, "reason": str(exc), "failures": {}}
    tolerance_issues = []
    for issue in issues:
        issue["measurements"] = {}
        group = None
        for frame in issue["frame_indices"]:
            failure = tolerances["failures"].get(f"{issue['camera']}/{issue['marker']}/{frame}")
            if failure is None:
                group = None
                continue
            issue["measurements"][str(frame)] = failure
            if (
                group is None
                or group["frame_indices"][-1] != frame - 1
                or group["reason"] != failure["reason"]
            ):
                group = {
                    **issue,
                    "frame_indices": [],
                    "measurements": {},
                    "reason": failure["reason"],
                    "camera_attribution": "camera_check_failed",
                    "start_time_s": frame / issue["fps"],
                }
                tolerance_issues.append(group)
            group["frame_indices"].append(frame)
            group["measurements"][str(frame)] = failure
            group["end_time_s"] = frame / issue["fps"]
    return {
        "diagnostic_only": True,
        "warning": (
            "Read-only diagnostic using saved phase anchors and current settings, "
            "not a replacement for saved results. A failed reprojection check may come from "
            "3D geometry or calibration even when the visible marker is correct. "
            "Frame links use each clip's saved frame rate, "
            "not verified cross-camera synchronization."
        ),
        "metrics": diagnostic["metrics"],
        "issues": issues,
        "tolerance_issues": tolerance_issues,
        "tolerance_check": {"available": tolerances["available"], "reason": tolerances["reason"]},
        "blockers": blockers,
    }


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
    metadata: dict = {}
    meta_path = session_dir / "metadata.json"
    if meta_path.exists():
        try:
            metadata = json.loads(meta_path.read_text())
            delay = metadata.get("pre_capture_delay_s")
            club = metadata.get("club")
            if delay is not None:
                phases = detect_phases(
                    seq,
                    impact_hint_frame=round(float(delay) * seq.fps),
                    reference=_reference_for_session(
                        seq, metadata, trc_path, config.analysis.golfer_handedness
                    ),
                )
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
                        refined = detect_phases(
                            seq,
                            impact_hint_frame=impact_frame,
                            reference=_reference_for_session(
                                seq, metadata, trc_path, config.analysis.golfer_handedness
                            ),
                        )
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

    camera_devices = getattr(getattr(config, "cameras", None), "devices", [])
    camera_roles = [device.role for device in camera_devices]
    reference = _reference_for_session(seq, metadata, trc_path, config.analysis.golfer_handedness)
    marker_support = _marker_observation_support(seq, session_dir, camera_roles, config.metrics)
    try:
        artifact = verified_artifact_evidence(trc_path)
    except (OSError, ValueError, KeyError):
        artifact = None
    if artifact is not None:
        reconstructed = {
            name: np.asarray(values, dtype=bool)
            for name, values in artifact.get("marker_support", {}).items()
        }
        if marker_support is None:
            marker_support = reconstructed
        else:
            for name, values in reconstructed.items():
                if name in marker_support and values.shape == marker_support[name].shape:
                    marker_support[name] &= values
    report = compute_metrics(
        seq,
        config.metrics,
        phases=phases,
        handedness=config.analysis.golfer_handedness,
        club=club,
        reference=reference,
        marker_support=marker_support,
    )
    tips = generate_tips(report)

    out_path = session_dir / "metrics.json"
    camera_wrist_visibility = _wrist_visibility_by_camera(
        session_dir,
        camera_roles,
        report.phases.address_frame,
        report.phases.impact_frame,
    )
    camera_wrist_triangulation_coverage = _wrist_visibility_by_camera(
        session_dir,
        camera_roles,
        report.phases.address_frame,
        report.phases.impact_frame,
        confidence_threshold=0.3,
    )
    tracking_quality = assess_tracking_quality(
        seq,
        swing_window=(report.phases.address_frame, report.phases.impact_frame),
        camera_wrist_visibility=camera_wrist_visibility,
        camera_wrist_triangulation_coverage=camera_wrist_triangulation_coverage,
        metric_confidence={metric.name: metric.status for metric in report.metrics},
        metric_reasons={metric.name: metric.reasons for metric in report.metrics if metric.reasons},
    )

    if artifact is not None and artifact.get("session_validation", {}).get("status") == "failed":
        tracking_quality.reliable = False
        tracking_quality.warnings.extend(artifact["session_validation"]["reasons"])
    payload = {
        "source_trc": trc_path.name,
        "reconstruction_validation": (
            None if artifact is None else artifact.get("session_validation")
        ),
        "club": club,
        "club_profile": config.metrics.club_profile_mapping.get(club) if club else None,
        # quality first so the UI can caveat everything below it when the
        # reconstruction is too poor to trust (see analysis.quality)
        "tracking_quality": tracking_quality.to_dict(),
        **report.to_dict(),
        "tips": tips_to_dicts(tips),
        "ball": ball_info,
        "p_positions": _p_positions_payload(seq, report, config, club=club),
    }
    out_path.write_text(json.dumps(payload, indent=2, allow_nan=False))
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
        value = "unavailable" if metric["value"] is None else f"{metric['value']} {metric['unit']}"
        print(f"  {metric['name']}: {value} [{metric.get('status', 'legacy-unverified')}]{flag}")

    print("\nP-positions:")
    for pos in report["p_positions"]:
        print(f"  {pos['name']} ({pos['label']}): frame {pos['frame_index']}, {pos['time_s']}s")

    if report["tips"]:
        print("\ntips:")
        for i, tip in enumerate(report["tips"], 1):
            print(f"  {i}. [{tip['metric']} {tip['direction']}] {tip['text']}")
    else:
        all_in_range = len(report["metrics"]) == 19 and all(
            metric["value"] is not None
            and metric.get("status") == "valid"
            and metric["range"] is not None
            and metric["in_range"] is True
            for metric in report["metrics"]
        )
        message = (
            "everything measured is in range. Nice swing."
            if all_in_range
            else (
                "assessment incomplete: some measurements could not be verified."
                if len(report["metrics"]) != 19
                or any(metric.get("status") != "valid" for metric in report["metrics"])
                else "no actionable tips for this swing."
            )
        )
        print(f"\n{message}")


if __name__ == "__main__":
    main()
