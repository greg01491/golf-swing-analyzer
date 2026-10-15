"""Orchestration for the in-app calibration wizard (see rig_calibration for
the math). Wizard captures are ordinary sessions marked with a
calibration_shot.json file; the compute step turns them into the rig's
Calib_rig.toml."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

import cv2

from golf_sim.config import Config, resolve_state_path
from golf_sim.pose.board_detect import count_board_in_clip, detect_board_corners
from golf_sim.pose.calibration_bundle import (
    activation_guard,
    atomic_json,
    camera_signatures,
    compare_signatures,
    load_active_bundle,
    publish_bundle,
)
from golf_sim.pose.rig_calibration import (
    RigCalibration,
    calibrate_extrinsics,
    calibrate_intrinsics,
    write_calib_toml,
)

logger = logging.getLogger(__name__)

MARKER = "calibration_shot.json"

# Calibration-quality gates: above these the calibration is unusable and is
# refused rather than silently saved (see compute_rig_calibration).
_MAX_LENS_RMS_PX = 5.0
_MAX_EXTRINSIC_REPROJ_PX = 50.0


def _save_preview_frame(video_path: Path, output_path: Path) -> None:
    """Save the first frame from a video as a preview image."""
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning(f"Cannot open video to extract preview: {video_path}")
            return
        ok, frame = cap.read()
        cap.release()
        if not ok:
            logger.warning(f"Cannot read first frame from {video_path}")
            return
        # Scale down to reasonable size (max 400px width) for preview
        h, w = frame.shape[:2]
        if w > 400:
            scale = 400 / w
            frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
        cv2.imwrite(str(output_path), frame)
        logger.debug(f"Saved preview frame to {output_path}")
    except Exception as e:
        logger.warning(f"Failed to save preview frame: {e}")


def mark_calibration_shot(
    session_dir: Path,
    kind: str,
    config: Config,
    for_camera: str | None = None,
    ground_confirmations: dict | None = None,
) -> dict:
    """Tag a captured session as a wizard shot; for intrinsics shots, run
    board detection per camera so the UI can give immediate feedback.

    for_camera records which camera the user was holding the board up to
    (the wizard's step 1 vs step 2) -- purely for per-stage progress
    counting in the UI. Without it, both steps counted the same pooled
    intrinsics total, so step 2 started at "8 / 8" after step 1's captures.
    The compute step deliberately still pools every shot regardless: each
    capture records both cameras, and board detection sorts out which
    camera actually saw the board."""
    corners = tuple(config.calibration.checkerboard_corners)
    board_counts = {}
    if kind == "intrinsics":
        for clip in sorted(Path(session_dir).glob("camera_*.mp4")):
            board_counts[clip.stem] = count_board_in_clip(clip, corners)

        # Save a preview frame from camera_1 to help user see what was captured
        camera_1_mp4 = Path(session_dir) / "camera_1.mp4"
        if camera_1_mp4.exists():
            preview_path = Path(session_dir) / "preview.jpg"
            _save_preview_frame(camera_1_mp4, preview_path)

    marker = {
        "kind": kind,
        "for_camera": for_camera,
        "board_frames_detected": board_counts,
        "samples_checked": 6,
    }
    if kind == "ground":
        bundle = load_active_bundle(resolve_state_path(config.calibration.dir))
        confirmations = ground_confirmations or {}
        if (
            bundle is None
            or confirmations.get("level_confirmed") is not True
            or confirmations.get("target_confirmed") is not True
        ):
            raise ValueError(
                "ground capture requires accepted camera geometry, "
                "a level board and marked target alignment"
            )
        marker.update(
            {"bundle_id": bundle["bundle_id"], "level_confirmed": True, "target_confirmed": True}
        )
        for role in ("camera_1", "camera_2"):
            video = cv2.VideoCapture(str(Path(session_dir) / f"{role}.mp4"))
            try:
                total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
                for sample in range(min(total, 24)):
                    video.set(cv2.CAP_PROP_POS_FRAMES, sample * total // min(total, 24))
                    ok, image = video.read()
                    found = (
                        detect_board_corners(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), corners)
                        if ok
                        else None
                    )
                    if found is None:
                        continue
                    points = found.reshape(-1, 2)
                    for label, point in (("FIRST", points[0]), ("LAST", points[-1])):
                        position = tuple(int(value) for value in point)
                        cv2.circle(image, position, 9, (0, 255, 255), 3)
                        cv2.putText(
                            image, label, position, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2
                        )
                    cv2.imwrite(str(Path(session_dir) / f"ground-preview-{role}.jpg"), image)
                    break
            finally:
                video.release()
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
                "for_camera": marker.get("for_camera"),
                "created_at": meta.get("created_at"),
                "board_frames_detected": marker.get("board_frames_detected", {}),
                "bundle_id": marker.get("bundle_id"),
            }
        )
    return shots


def clear_calibration_shots(data_dir: Path) -> int:
    """Deletes every wizard-captured session (both kinds) so a fresh
    calibration attempt starts from nothing -- otherwise stale captures from
    before a rig change (e.g. a camera rotation fix) silently keep feeding
    compute_rig_calibration alongside new ones, since intrinsics shots are
    pooled across every capture ever taken, not just the latest run."""
    deleted = 0
    for shot in list_calibration_shots(data_dir):
        session_dir = Path(data_dir) / "sessions" / shot["id"]
        shutil.rmtree(session_dir, ignore_errors=True)
        deleted += 1
    return deleted


def compute_rig_calibration(
    data_dir: Path,
    config: Config,
    camera_distance_m: float,
    on_stage=lambda msg: None,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict:
    """Full wizard computation. Returns a result summary dict; raises
    CalibrationDataError with actionable messages when captures are unusable."""
    from golf_sim.pose.estimate import run_pose_estimation
    from golf_sim.pose.rig_calibration import CalibrationDataError

    shots = list_calibration_shots(data_dir)
    if cancelled():
        raise CalibrationDataError("camera validation cancelled; active calibration unchanged")
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
        validation=config.calibration.validation,
    )
    on_stage("calibrating camera_2 lens")
    cam2 = calibrate_intrinsics(
        [d / "camera_2.mp4" for d in intrinsic_dirs if (d / "camera_2.mp4").exists()],
        corners,
        square,
        validation=config.calibration.validation,
    )

    on_stage("detecting body keypoints in the camera-position shot (takes ~1 min)")
    run_pose_estimation(extrinsic_dir, config.pose)

    on_stage("solving camera positions")
    pose_dir = extrinsic_dir / "pose2sim" / "pose"
    metadata = json.loads((extrinsic_dir / "metadata.json").read_text())
    captured_cameras = metadata.get("cameras", {})
    frame_rates = {camera.get("fps") for camera in captured_cameras.values()}
    if len(frame_rates) != 1 or None in frame_rates:
        raise CalibrationDataError(
            "camera-position capture requires matching recorded frame-rate grids"
        )
    signatures = camera_signatures(config, metadata)
    for directory in intrinsic_dirs:
        shot_metadata = json.loads((directory / "metadata.json").read_text())
        compatibility = compare_signatures(signatures, camera_signatures(config, shot_metadata))
        if compatibility["status"] == "incompatible":
            raise CalibrationDataError(
                "incompatible lens/camera captures: " + "; ".join(compatibility["reasons"])
            )
    validation_report = {}
    try:
        rotation, translation, n_points, reproj_err, height = calibrate_extrinsics(
            pose_dir,
            cam1,
            cam2,
            camera_distance_m,
            validation=config.calibration.validation,
            frame_rate_hz=next(iter(frame_rates)),
            validation_report=validation_report,
        )
    except CalibrationDataError as error:
        atomic_json(
            resolve_state_path(config.calibration.dir) / "last-candidate.json",
            {
                "status": "failed",
                "error": str(error),
                "validation": error.validation_report,
                "capture_id": extrinsic_dir.name,
            },
        )
        on_stage("camera validation failed; active calibration unchanged")
        raise

    # Reject an unusable calibration BEFORE writing it -- otherwise a broken
    # calibration (seen live: 580,000px reprojection error, from poor
    # checkerboard captures) is saved silently and corrupts the 3D of every
    # session that uses it, showing as garbage skeletons / metres-long bones.
    problems = []
    if (
        cam1.rms_error > config.calibration.validation.max_lens_rms_px
        or cam2.rms_error > config.calibration.validation.max_lens_rms_px
    ):
        problems.append(
            f"lens calibration is poor (camera_1 {cam1.rms_error:.1f}px, "
            f"camera_2 {cam2.rms_error:.1f}px; a good one is under ~1px). Redo the board "
            "steps: hold the FULL printed board flat and still, filling more of the frame, "
            "at several angles/distances, well lit and in sharp focus."
        )
    if reproj_err > _MAX_EXTRINSIC_REPROJ_PX:
        problems.append(
            f"the camera-position solve failed ({reproj_err:.0f}px reprojection; a good one "
            f"is under ~{_MAX_EXTRINSIC_REPROJ_PX:.0f}px). Redo the position step with your "
            "WHOLE body (head to feet) clearly visible in BOTH camera previews through a slow "
            "practice swing, and double-check the measured camera-to-camera distance."
        )
    if problems:
        raise CalibrationDataError(
            "Calibration is not usable, so it was NOT saved (your previous one is unchanged):\n- "
            + "\n- ".join(problems)
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
    validation_report["lenses"] = {"camera_1": cam1.validation, "camera_2": cam2.validation}
    rig_dir = resolve_state_path(config.calibration.dir)
    rig_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="candidate-", dir=rig_dir) as temporary:
        candidate = Path(temporary) / "Calib_rig.toml"
        write_calib_toml(candidate, rig)
        with activation_guard():
            if cancelled():
                raise CalibrationDataError(
                    "camera validation cancelled; active calibration unchanged"
                )
            accepted = publish_bundle(rig_dir, candidate, validation_report, signatures)
            on_stage("camera calibration accepted")
    calib_path = Path(accepted["calib_file"])

    return {
        "calib_file": str(calib_path),
        "camera_1": {"lens_views": cam1.n_views, "lens_rms_px": round(cam1.rms_error, 3)},
        "camera_2": {"lens_views": cam2.n_views, "lens_rms_px": round(cam2.rms_error, 3)},
        "keypoint_correspondences": n_points,
        "mean_reprojection_error_px": round(reproj_err, 2),
        "estimated_person_height_m": None if height is None else round(height, 2),
        "bundle_id": accepted["bundle_id"],
        "validation": validation_report,
        "compatibility": compare_signatures(signatures, camera_signatures(config)),
        "ground_status": "unavailable",
    }
