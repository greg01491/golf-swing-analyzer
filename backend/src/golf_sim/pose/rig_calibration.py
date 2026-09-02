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
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from golf_sim.pose.board_detect import find_board_corners


@dataclass
class CameraIntrinsics:
    matrix: np.ndarray  # 3x3
    distortions: np.ndarray  # 4-vector
    size: tuple[int, int]  # (w, h)
    rms_error: float
    n_views: int


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
    pass


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
    clips: list[Path], corners_nb: tuple[int, int], square_size_mm: float
) -> CameraIntrinsics:
    rows, cols = corners_nb
    object_points_single = np.zeros((rows * cols, 3), np.float32)
    object_points_single[:, :2] = (
        np.mgrid[0:rows, 0:cols].T.reshape(-1, 2) * square_size_mm / 1000.0
    )

    image_points, size = [], None
    for clip in clips:
        for corners, img_size in find_board_corners(clip, corners_nb):
            image_points.append(corners)
            size = img_size
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

    return CameraIntrinsics(
        matrix=matrix,
        distortions=dist.ravel()[:4],
        size=size,
        rms_error=float(rms),
        n_views=len(image_points),
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
    frames1 = sorted(dirs[0].glob("*.json"))
    frames2 = sorted(dirs[1].glob("*.json"))

    pts1, pts2, frame_ids, joint_ids = [], [], [], []
    for frame_no, (f1, f2) in enumerate(zip(frames1, frames2, strict=False)):
        people1 = json.loads(f1.read_text())["people"]
        people2 = json.loads(f2.read_text())["people"]
        if len(people1) != 1 or len(people2) != 1:
            continue  # ambiguous frame -- skip rather than risk wrong matches
        kp1 = np.array(people1[0]["pose_keypoints_2d"]).reshape(-1, 3)
        kp2 = np.array(people2[0]["pose_keypoints_2d"]).reshape(-1, 3)
        good = (kp1[:, 2] > confidence_threshold) & (kp2[:, 2] > confidence_threshold)
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
) -> tuple[np.ndarray, np.ndarray, int, float, float | None]:
    """Relative pose of camera_2 in camera_1's frame from person keypoints.

    Returns (rodrigues rotation, translation [m], n_points, mean reprojection
    error px, estimated standing height m or None)."""
    pts1, pts2, frame_ids, joint_ids = _load_keypoint_correspondences(pose_dir)
    if len(pts1) < 100:
        raise CalibrationDataError(
            f"only {len(pts1)} keypoint correspondences -- capture again with the "
            "whole body visible in both cameras (a slow practice swing helps)"
        )

    n1 = cv2.undistortPoints(pts1.reshape(-1, 1, 2), cam1.matrix, cam1.distortions)
    n2 = cv2.undistortPoints(pts2.reshape(-1, 1, 2), cam2.matrix, cam2.distortions)
    E, inliers = cv2.findEssentialMat(
        n1, n2, np.eye(3), method=cv2.RANSAC, prob=0.999, threshold=1e-3
    )
    if E is None:
        raise CalibrationDataError("essential matrix estimation failed -- recapture")
    _, R, t, pose_mask = cv2.recoverPose(E, n1, n2, np.eye(3), mask=inliers)
    t = t.ravel() / np.linalg.norm(t) * camera_distance_m

    # triangulate inlier correspondences for validation
    P1 = np.hstack([np.eye(3), np.zeros((3, 1))])
    P2 = np.hstack([R, t.reshape(3, 1)])
    mask = pose_mask.ravel().astype(bool)
    n1_in, n2_in = n1.reshape(-1, 2)[mask], n2.reshape(-1, 2)[mask]
    points4 = cv2.triangulatePoints(P1, P2, n1_in.T, n2_in.T)
    points3 = (points4[:3] / points4[3]).T

    # reprojection error in pixels (view 1)
    reproj, _ = cv2.projectPoints(points3, np.zeros(3), np.zeros(3), cam1.matrix, cam1.distortions)
    orig = pts1[mask]
    err = float(np.mean(np.linalg.norm(reproj.reshape(-1, 2) - orig, axis=1)))

    # rough standing-height sanity figure, from the most upright frame
    height = _estimate_standing_height(points3, frame_ids[mask], joint_ids[mask])

    return cv2.Rodrigues(R)[0].ravel(), t, int(mask.sum()), err, height


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
