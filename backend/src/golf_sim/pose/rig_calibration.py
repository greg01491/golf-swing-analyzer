"""Two-camera rig calibration from wizard captures (replaces Pose2Sim's
board-based extrinsic flow, which needs a board far bigger than A4 at
golf-rig distances).

- Intrinsics per camera: close-up checkerboard shots -> cv2.calibrateCamera.
- Extrinsics: a synchronized capture of a *person* at the hitting position
  (ideally doing a slow practice swing -- the motion sweeps the shared view
  volume). Matched 2D pose keypoints across the two views give point
  correspondences; the essential matrix recovers relative camera pose, and
  the user-measured camera-to-camera distance anchors metric scale. The
  world frame is camera_1's frame -- arbitrary orientation is fine because
  the metrics engine infers "up" from the body itself.

Output: Calib_rig.toml in the format Pose2Sim's triangulation reads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from golf_sim.config import CalibrationValidationConfig
from golf_sim.pose.board_detect import find_board_corners


@dataclass
class CameraIntrinsics:
    matrix: np.ndarray  # 3x3
    distortions: np.ndarray  # 4-vector
    size: tuple[int, int]  # (w, h)
    rms_error: float
    n_views: int
    validation: dict = field(default_factory=dict)


@dataclass
class RigCalibration:
    cam1: CameraIntrinsics
    cam2: CameraIntrinsics
    rotation_cam2: np.ndarray  # rodrigues 3-vector, cam1 frame -> cam2
    translation_cam2: np.ndarray  # metres
    n_correspondences: int
    mean_reprojection_error_px: float
    estimated_person_height_m: float | None


class CalibrationDataError(RuntimeError):
    def __init__(self, message: str, validation_report: dict | None = None):
        super().__init__(message)
        self.validation_report = validation_report


#: A view whose reprojection error exceeds max(3x the median, this) is treated
#: as a bad capture -- motion blur, or the board clipped by the frame edge.
_OUTLIER_FLOOR_PX = 0.5
_MIN_VIEWS_AFTER_REJECTION = 12
_MAX_REJECTION_ROUNDS = 3


def _per_view_errors(object_points, image_points, matrix, dist, rvecs, tvecs) -> np.ndarray:
    """Mean reprojection error for each board view, in pixels."""
    errors = []
    for objp, imgp, rvec, tvec in zip(object_points, image_points, rvecs, tvecs, strict=True):
        projected, _ = cv2.projectPoints(objp, rvec, tvec, matrix, dist)
        errors.append(cv2.norm(imgp, projected.reshape(imgp.shape), cv2.NORM_L2) / len(projected))
    return np.array(errors)


def calibrate_intrinsics(
    clips: list[Path],
    corners_nb: tuple[int, int],
    square_size_mm: float,
    validation: CalibrationValidationConfig | None = None,
) -> CameraIntrinsics:
    rows, cols = corners_nb
    object_points_single = np.zeros((rows * cols, 3), np.float32)
    object_points_single[:, :2] = (
        np.mgrid[0:rows, 0:cols].T.reshape(-1, 2) * square_size_mm / 1000.0
    )

    image_points, size = [], None
    groups = []
    for clip in clips:
        for corners, img_size in find_board_corners(clip, corners_nb):
            if size is not None and img_size != size:
                raise CalibrationDataError("lens captures have incompatible image dimensions")
            image_points.append(corners)
            groups.append(str(clip))
            size = img_size
    heldout_points = []
    if validation is not None:
        unique_groups = list(dict.fromkeys(groups))
        if len(unique_groups) < 2:
            raise CalibrationDataError(
                "held-out lens validation requires independent capture clips"
            )
        count = max(1, int(np.ceil(len(unique_groups) * validation.heldout_fraction)))
        withheld = set(unique_groups[-count:])
        heldout_points = [
            points for points, group in zip(image_points, groups, strict=True) if group in withheld
        ]
        image_points = [
            points
            for points, group in zip(image_points, groups, strict=True)
            if group not in withheld
        ]
        if len(heldout_points) < 6:
            raise CalibrationDataError(
                "held-out lens validation needs at least six usable board views"
            )
    if len(image_points) < 6:
        raise CalibrationDataError(
            f"only {len(image_points)} usable board views across {len(clips)} clip(s) -- "
            "need at least 6. Hold the board closer to the lens (about arm's length), "
            "well lit, tilting slowly."
        )

    # Fix k3 at zero: the Pose2Sim Calib toml stores exactly four distortion
    # coefficients, so fitting a fifth and then slicing it off would persist a
    # lens model that was never fitted. On the live rig k3 came out at -63.6
    # for the wide camera, so that truncation was badly wrong, not cosmetic.
    flags = cv2.CALIB_FIX_K3
    object_points = [object_points_single] * len(image_points)
    rms, matrix, dist, rvecs, tvecs = cv2.calibrateCamera(
        object_points, image_points, size, None, None, flags=flags
    )

    # A few bad views can dominate the fit: on the live rig 12 blurred views
    # out of 191 pushed the wide camera to 7.1px, which tripped the "poor
    # calibration" guard, while the other 179 fitted to 0.48px. Drop the
    # outliers and refit rather than rejecting a perfectly usable capture set.
    for _ in range(_MAX_REJECTION_ROUNDS):
        errors = _per_view_errors(object_points, image_points, matrix, dist, rvecs, tvecs)
        keep = errors <= max(float(np.median(errors)) * 3, _OUTLIER_FLOOR_PX)
        if keep.all() or int(keep.sum()) < _MIN_VIEWS_AFTER_REJECTION:
            break
        image_points = [p for p, keeping in zip(image_points, keep, strict=True) if keeping]
        object_points = [object_points_single] * len(image_points)
        rms, matrix, dist, rvecs, tvecs = cv2.calibrateCamera(
            object_points, image_points, size, None, None, flags=flags
        )

    lens_validation = {"status": "legacy-unverified"}
    if validation is not None:
        residuals = []
        for observed in heldout_points:
            ok, rotation, translation = cv2.solvePnP(object_points_single, observed, matrix, dist)
            if not ok:
                residuals.append(float("inf"))
                continue
            projected, _ = cv2.projectPoints(
                object_points_single, rotation, translation, matrix, dist
            )
            residuals.extend(
                np.linalg.norm(projected.reshape(-1, 2) - observed.reshape(-1, 2), axis=1)
            )
        errors = np.asarray(residuals)
        if (
            not np.isfinite(errors).all()
            or np.median(errors) > validation.max_median_error_px
            or np.percentile(errors, 95) > validation.max_tail_error_px
            or rms > validation.max_lens_rms_px
        ):
            raise CalibrationDataError("held-out lens reprojection validation failed")
        lens_validation = {
            "status": "accepted",
            "fit_views": len(image_points),
            "heldout_views": len(heldout_points),
            "median_px": float(np.median(errors)),
            "p95_px": float(np.percentile(errors, 95)),
            "heldout_captures": sorted(withheld),
        }
    return CameraIntrinsics(
        matrix=matrix,
        distortions=dist.ravel()[:4],
        size=size,
        rms_error=float(rms),
        n_views=len(image_points),
        validation=lens_validation,
    )


# HALPE_26 indices, the layout Pose2Sim emits by default.
_HALPE_26_JOINTS = 26
_HEAD_JOINTS = (17, 0)  # Head, falling back to Nose
_FOOT_JOINTS = (24, 25, 15, 16)  # heels, then ankles


def _load_keypoint_correspondences(
    pose_dir: Path, confidence_threshold: float = 0.6
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Matched (x, y) keypoints between camera_1 and camera_2 across all
    frames of a pose-estimated session.

    Also returns, parallel to the points, the frame number and the joint index
    each correspondence came from, so callers can reason about individual body
    parts rather than an anonymous point cloud."""
    dirs = sorted(pose_dir.glob("camera_*_json"))
    if len(dirs) != 2:
        raise CalibrationDataError(f"expected 2 camera json folders in {pose_dir}, got {len(dirs)}")
    frames1 = {int(path.stem.rsplit("_", 1)[-1]): path for path in dirs[0].glob("*.json")}
    frames2 = {int(path.stem.rsplit("_", 1)[-1]): path for path in dirs[1].glob("*.json")}

    pts1, pts2, frame_ids, joint_ids = [], [], [], []
    for frame_no in sorted(frames1.keys() & frames2.keys()):
        f1, f2 = frames1[frame_no], frames2[frame_no]
        people1 = json.loads(f1.read_text())["people"]
        people2 = json.loads(f2.read_text())["people"]
        if len(people1) != 1 or len(people2) != 1:
            continue  # ambiguous frame -- skip rather than risk wrong matches
        kp1 = np.array(people1[0]["pose_keypoints_2d"]).reshape(-1, 3)
        kp2 = np.array(people2[0]["pose_keypoints_2d"]).reshape(-1, 3)
        if kp1.shape != kp2.shape:
            continue
        good = (kp1[:, 2] > confidence_threshold) & (kp2[:, 2] > confidence_threshold)
        good &= np.isfinite(kp1).all(axis=1) & np.isfinite(kp2).all(axis=1)
        pts1.append(kp1[good, :2])
        pts2.append(kp2[good, :2])
        joints = np.flatnonzero(good)
        joint_ids.append(joints)
        frame_ids.append(np.full(len(joints), frame_no))
    if not pts1:
        raise CalibrationDataError("no frames where exactly one person is visible in both views")
    return (
        np.vstack(pts1).astype(np.float64),
        np.vstack(pts2).astype(np.float64),
        np.concatenate(frame_ids),
        np.concatenate(joint_ids),
    )


def _estimate_standing_height(
    points3: np.ndarray, frame_ids: np.ndarray, joint_ids: np.ndarray
) -> float | None:
    """Tallest head-to-feet distance over the capture, in metres.

    The old sanity figure was the largest side of the bounding box of every
    triangulated point from every frame, which measures the volume the golfer
    swept through (arms, club, any drift) rather than the golfer, and so reads
    high. Measuring head to feet within a single frame is a real anthropometric
    quantity, and the most upright frame of the capture approximates standing
    height."""
    if joint_ids.size == 0 or joint_ids.max() >= _HALPE_26_JOINTS:
        return None  # unknown skeleton layout -- don't guess

    spans = []
    for frame in np.unique(frame_ids):
        in_frame = frame_ids == frame
        joints = joint_ids[in_frame]
        coords = points3[in_frame]
        lookup = {int(j): coords[i] for i, j in enumerate(joints)}
        head = next((lookup[j] for j in _HEAD_JOINTS if j in lookup), None)
        feet = [lookup[j] for j in _FOOT_JOINTS if j in lookup]
        if head is None or not feet:
            continue
        spans.append(float(np.linalg.norm(head - np.mean(feet, axis=0))))

    if len(spans) < 5:
        return None
    # the most upright frame, but via a high percentile so one bad
    # triangulation can't set the answer
    return float(np.percentile(spans, 95))


def calibrate_extrinsics(
    pose_dir: Path,
    cam1: CameraIntrinsics,
    cam2: CameraIntrinsics,
    camera_distance_m: float,
    validation: CalibrationValidationConfig | None = None,
    frame_rate_hz: float | None = None,
    validation_report: dict | None = None,
) -> tuple[np.ndarray, np.ndarray, int, float, float | None]:
    """Relative pose of camera_2 in camera_1's frame from person keypoints.

    Returns (rodrigues rotation, translation [m], n_points, mean reprojection
    error px, estimated standing height m or None)."""
    if not np.isfinite(camera_distance_m) or not 0.3 < camera_distance_m < 20:
        raise CalibrationDataError("measured camera separation must be between 0.3 and 20 metres")
    pts1, pts2, frame_ids, joint_ids = _load_keypoint_correspondences(pose_dir)
    settings = validation if validation is not None else CalibrationValidationConfig()
    if len(pts1) < settings.min_fit_correspondences:
        raise CalibrationDataError(
            f"only {len(pts1)} keypoint correspondences -- capture again with the "
            "whole body visible in both cameras (a slow practice swing helps)"
        )
    if frame_rate_hz is None or not np.isfinite(frame_rate_hz) or frame_rate_hz <= 0:
        raise CalibrationDataError("held-out validation requires the recorded capture frame rate")
    frames = np.unique(frame_ids)
    heldout_count = max(
        settings.min_heldout_frames, int(np.ceil(len(frames) * settings.heldout_fraction))
    )
    if heldout_count >= len(frames):
        raise CalibrationDataError("insufficient independent frames for held-out validation")
    heldout_start = frames[-heldout_count]
    fitting = frame_ids < heldout_start - settings.partition_gap_s * frame_rate_hz
    heldout = frame_ids >= heldout_start
    if (
        fitting.sum() < settings.min_fit_correspondences
        or heldout.sum() < settings.min_heldout_correspondences
    ):
        raise CalibrationDataError(
            "insufficient correspondences after the held-out partition and time gap"
        )

    n1 = cv2.undistortPoints(pts1.reshape(-1, 1, 2), cam1.matrix, cam1.distortions)
    n2 = cv2.undistortPoints(pts2.reshape(-1, 1, 2), cam2.matrix, cam2.distortions)
    E, inliers = cv2.findEssentialMat(
        n1[fitting], n2[fitting], np.eye(3), method=cv2.RANSAC, prob=0.999, threshold=1e-3
    )
    if E is None:
        raise CalibrationDataError("essential matrix estimation failed -- recapture")
    _, R, t, pose_mask = cv2.recoverPose(E, n1[fitting], n2[fitting], np.eye(3), mask=inliers)
    if pose_mask is None or int(np.count_nonzero(pose_mask)) < settings.min_fit_correspondences:
        raise CalibrationDataError(
            "insufficient positive-depth fitting correspondences for held-out validation"
        )
    t = t.ravel() / np.linalg.norm(t) * camera_distance_m

    # triangulate inlier correspondences for validation
    P1 = np.hstack([np.eye(3), np.zeros((3, 1))])
    P2 = np.hstack([R, t.reshape(3, 1)])
    mask = np.zeros(len(pts1), dtype=bool)
    mask[np.flatnonzero(fitting)] = pose_mask.ravel().astype(bool)
    n1_in, n2_in = n1.reshape(-1, 2)[mask], n2.reshape(-1, 2)[mask]
    points4 = cv2.triangulatePoints(P1, P2, n1_in.T, n2_in.T)
    points3 = (points4[:3] / points4[3]).T

    # reprojection error in pixels (view 1)
    reproj, _ = cv2.projectPoints(points3, np.zeros(3), np.zeros(3), cam1.matrix, cam1.distortions)
    orig = pts1[mask]
    err = float(np.mean(np.linalg.norm(reproj.reshape(-1, 2) - orig, axis=1)))

    # rough standing-height sanity figure, from the most upright frame
    height = _estimate_standing_height(points3, frame_ids[mask], joint_ids[mask])

    report = evaluate_camera_geometry(
        pts1[heldout],
        pts2[heldout],
        joint_ids[heldout],
        cam1,
        cam2,
        cv2.Rodrigues(R)[0].ravel(),
        t,
        settings,
        frame_ids=frame_ids[heldout],
    )
    report.update(
        {
            "version": 1,
            "fit_count": int(fitting.sum()),
            "fit_inliers": int(mask.sum()),
            "fit_error_px": err,
            "heldout_count": int(heldout.sum()),
            "heldout_frames": frames[-heldout_count:].tolist(),
            "fit_frames": np.unique(frame_ids[fitting]).tolist(),
            "partition_gap_s": settings.partition_gap_s,
            "baseline_m": float(np.linalg.norm(t)),
            "scale_status": "baseline_only",
            "ground_status": "unavailable",
        }
    )
    if validation_report is not None:
        validation_report.update(report)
    if report["status"] != "accepted":
        raise CalibrationDataError(
            "held-out validation failed: " + "; ".join(report["reasons"]), validation_report=report
        )

    return cv2.Rodrigues(R)[0].ravel(), t, int(mask.sum()), err, height


def evaluate_camera_geometry(
    first: np.ndarray,
    second: np.ndarray,
    joint_ids: np.ndarray,
    cam1: CameraIntrinsics,
    cam2: CameraIntrinsics,
    rotation: np.ndarray,
    translation: np.ndarray,
    settings: CalibrationValidationConfig,
    frame_ids: np.ndarray | None = None,
) -> dict:
    if not len(first):
        return {
            "status": "failed",
            "reasons": ["no independent observations"],
            "cameras": {},
            "positive_depth_coverage": 0.0,
        }
    normalized = [
        cv2.undistortPoints(points.reshape(-1, 1, 2), camera.matrix, camera.distortions).reshape(
            -1, 2
        )
        for points, camera in ((first, cam1), (second, cam2))
    ]
    rotation_matrix = cv2.Rodrigues(rotation)[0]
    homogeneous = cv2.triangulatePoints(
        np.column_stack((np.eye(3), np.zeros(3))),
        np.column_stack((rotation_matrix, translation)),
        normalized[0].T,
        normalized[1].T,
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        points3 = (homogeneous[:3] / homogeneous[3]).T
    positive = np.isfinite(points3).all(axis=1) & (points3[:, 2] > 0)
    positive &= (points3 @ rotation_matrix.T + translation)[:, 2] > 0
    cameras = {}
    regions = {
        "shoulders": (5, 6),
        "pelvis": (11, 12, 19),
        "head": (0, 17, 18),
        "legs": (13, 14, 15, 16),
    }
    reasons = []
    for role, camera, observed, camera_rotation, camera_translation in (
        ("camera_1", cam1, first, np.zeros(3), np.zeros(3)),
        ("camera_2", cam2, second, rotation, translation),
    ):
        projected, _ = cv2.projectPoints(
            points3, camera_rotation, camera_translation, camera.matrix, camera.distortions
        )
        errors = np.linalg.norm(projected.reshape(-1, 2) - observed, axis=1)
        errors[~positive | ~np.isfinite(errors)] = np.inf
        finite = errors[np.isfinite(errors)]
        median = float(np.median(finite)) if finite.size else None
        tail = float(np.percentile(finite, 95)) if finite.size else None
        coverage = float((errors <= settings.max_tail_error_px).mean()) if errors.size else 0.0
        region_coverage = {}
        for region, indices in regions.items():
            selected = np.isin(joint_ids, indices)
            expected = (
                len(np.unique(frame_ids)) * len(indices)
                if frame_ids is not None
                else int(selected.sum())
            )
            accepted = int((errors[selected] <= settings.max_tail_error_px).sum())
            region_coverage[region] = min(1.0, accepted / expected) if expected else 0.0
            if region_coverage[region] < settings.min_coverage:
                reasons.append(f"{role} {region} coverage is {region_coverage[region]:.0%}")
        if (
            median is None
            or median > settings.max_median_error_px
            or tail > settings.max_tail_error_px
            or coverage < settings.min_coverage
        ):
            reasons.append(f"{role} reprojection error/coverage exceeds limits")
        cameras[role] = {
            "median_px": median,
            "p95_px": tail,
            "coverage": coverage,
            "regions": region_coverage,
        }
    depth_coverage = float(positive.mean()) if positive.size else 0.0
    if depth_coverage < settings.min_positive_depth:
        reasons.append("positive depth coverage is insufficient")
    return {
        "status": "failed" if reasons else "accepted",
        "reasons": reasons,
        "cameras": cameras,
        "positive_depth_coverage": depth_coverage,
    }


def write_calib_toml(path: Path, rig: RigCalibration) -> None:
    def cam_block(name: str, intr: CameraIntrinsics, rot: np.ndarray, trans: np.ndarray) -> str:
        matrix = ", ".join("[" + ", ".join(f"{v:.6f}" for v in row) + "]" for row in intr.matrix)
        return (
            f"[{name}]\n"
            f'name = "{name}"\n'
            f"size = [{float(intr.size[0])}, {float(intr.size[1])}]\n"
            f"matrix = [{matrix}]\n"
            f"distortions = [{', '.join(f'{v:.6f}' for v in intr.distortions)}]\n"
            f"rotation = [{', '.join(f'{v:.6f}' for v in rot)}]\n"
            f"translation = [{', '.join(f'{v:.6f}' for v in trans)}]\n"
            f"fisheye = false\n\n"
        )

    content = (
        cam_block("camera_1", rig.cam1, np.zeros(3), np.zeros(3))
        + cam_block("camera_2", rig.cam2, rig.rotation_cam2, rig.translation_cam2)
        + "[metadata]\n"
        + f"n_correspondences = {rig.n_correspondences}\n"
        + f"mean_reprojection_error_px = {rig.mean_reprojection_error_px:.3f}\n"
    )
    path.write_text(content)
