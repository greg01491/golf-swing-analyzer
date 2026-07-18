"""Orchestration for the in-app calibration wizard (see rig_calibration for
the math). Wizard captures are ordinary sessions marked with a
calibration_shot.json file; the compute step turns them into the rig's
Calib_rig.toml."""

from __future__ import annotations

import json
from pathlib import Path

from golf_sim.config import REPO_ROOT, Config
from golf_sim.pose.board_detect import count_board_in_clip
from golf_sim.pose.rig_calibration import (
    RigCalibration,
    calibrate_extrinsics,
    calibrate_intrinsics,
    write_calib_toml,
)

MARKER = "calibration_shot.json"


def mark_calibration_shot(session_dir: Path, kind: str, config: Config) -> dict:
    """Tag a captured session as a wizard shot; for intrinsics shots, run
    board detection per camera so the UI can give immediate feedback."""
    corners = tuple(config.calibration.checkerboard_corners)
    board_counts = {}
    if kind == "intrinsics":
        for clip in sorted(Path(session_dir).glob("camera_*.mp4")):
            board_counts[clip.stem] = count_board_in_clip(clip, corners)
    marker = {"kind": kind, "board_frames_detected": board_counts, "samples_checked": 6}
    (Path(session_dir) / MARKER).write_text(json.dumps(marker, indent=2))
    return marker


def list_calibration_shots(data_dir: Path) -> list[dict]:
    root = Path(data_dir) / "sessions"
    if not root.is_dir():
        return []
    shots = []
    for session_dir in sorted(root.iterdir()):
        marker_path = session_dir / MARKER
        if not marker_path.exists():
            continue
        try:
            marker = json.loads(marker_path.read_text())
            meta = json.loads((session_dir / "metadata.json").read_text())
        except (json.JSONDecodeError, OSError):
            continue
        shots.append(
            {
                "id": session_dir.name,
                "kind": marker.get("kind"),
                "created_at": meta.get("created_at"),
                "board_frames_detected": marker.get("board_frames_detected", {}),
            }
        )
    return shots


def compute_rig_calibration(
    data_dir: Path, config: Config, camera_distance_m: float, on_stage=lambda msg: None
) -> dict:
    """Full wizard computation. Returns a result summary dict; raises
    CalibrationDataError with actionable messages when captures are unusable."""
    from golf_sim.pose.estimate import run_pose_estimation
    from golf_sim.pose.rig_calibration import CalibrationDataError

    shots = list_calibration_shots(data_dir)
    root = Path(data_dir) / "sessions"
    intrinsic_dirs = [root / s["id"] for s in shots if s["kind"] == "intrinsics"]
    extrinsic_shots = [s for s in shots if s["kind"] == "extrinsics"]
    if not intrinsic_dirs:
        raise CalibrationDataError("no lens (intrinsics) shots captured yet")
    if not extrinsic_shots:
        raise CalibrationDataError("no camera-position (extrinsics) shot captured yet")
    extrinsic_dir = root / extrinsic_shots[-1]["id"]  # latest wins

    corners = tuple(config.calibration.checkerboard_corners)
    square = config.calibration.checkerboard_square_size_mm

    on_stage("calibrating camera_1 lens")
    cam1 = calibrate_intrinsics(
        [d / "camera_1.mp4" for d in intrinsic_dirs if (d / "camera_1.mp4").exists()],
        corners,
        square,
    )
    on_stage("calibrating camera_2 lens")
    cam2 = calibrate_intrinsics(
        [d / "camera_2.mp4" for d in intrinsic_dirs if (d / "camera_2.mp4").exists()],
        corners,
        square,
    )

    on_stage("detecting body keypoints in the camera-position shot (takes ~1 min)")
    run_pose_estimation(extrinsic_dir, config.pose)

    on_stage("solving camera positions")
    pose_dir = extrinsic_dir / "pose2sim" / "pose"
    rotation, translation, n_points, reproj_err, height = calibrate_extrinsics(
        pose_dir, cam1, cam2, camera_distance_m
    )

    rig = RigCalibration(
        cam1=cam1,
        cam2=cam2,
        rotation_cam2=rotation,
        translation_cam2=translation,
        n_correspondences=n_points,
        mean_reprojection_error_px=reproj_err,
        estimated_person_height_m=height,
    )
    rig_dir = Path(config.calibration.dir)
    if not rig_dir.is_absolute():
        rig_dir = REPO_ROOT / rig_dir
    rig_dir.mkdir(parents=True, exist_ok=True)
    calib_path = rig_dir / "Calib_rig.toml"
    write_calib_toml(calib_path, rig)

    return {
        "calib_file": str(calib_path),
        "camera_1": {"lens_views": cam1.n_views, "lens_rms_px": round(cam1.rms_error, 3)},
        "camera_2": {"lens_views": cam2.n_views, "lens_rms_px": round(cam2.rms_error, 3)},
        "keypoint_correspondences": n_points,
        "mean_reprojection_error_px": round(reproj_err, 2),
        "estimated_person_height_m": None if height is None else round(height, 2),
    }
