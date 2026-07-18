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
    object_points = [object_points_single] * len(image_points)
    rms, K, dist, _, _ = cv2.calibrateCamera(object_points, image_points, size, None, None)
    return CameraIntrinsics(
        matrix=K,
        distortions=dist.ravel()[:4],
        size=size,
        rms_error=float(rms),
        n_views=len(image_points),
    )


def _load_keypoint_correspondences(
    pose_dir: Path, confidence_threshold: float = 0.6
) -> tuple[np.ndarray, np.ndarray]:
    """Matched (x, y) keypoints between camera_1 and camera_2 across all
    frames of a pose-estimated session."""
    dirs = sorted(pose_dir.glob("camera_*_json"))
    if len(dirs) != 2:
        raise CalibrationDataError(f"expected 2 camera json folders in {pose_dir}, got {len(dirs)}")
    frames1 = sorted(dirs[0].glob("*.json"))
    frames2 = sorted(dirs[1].glob("*.json"))

    pts1, pts2 = [], []
    for f1, f2 in zip(frames1, frames2, strict=False):
        people1 = json.loads(f1.read_text())["people"]
        people2 = json.loads(f2.read_text())["people"]
        if len(people1) != 1 or len(people2) != 1:
            continue  # ambiguous frame -- skip rather than risk wrong matches
        kp1 = np.array(people1[0]["pose_keypoints_2d"]).reshape(-1, 3)
        kp2 = np.array(people2[0]["pose_keypoints_2d"]).reshape(-1, 3)
        good = (kp1[:, 2] > confidence_threshold) & (kp2[:, 2] > confidence_threshold)
        pts1.append(kp1[good, :2])
        pts2.append(kp2[good, :2])
    if not pts1:
        raise CalibrationDataError("no frames where exactly one person is visible in both views")
    return np.vstack(pts1).astype(np.float64), np.vstack(pts2).astype(np.float64)


def calibrate_extrinsics(
    pose_dir: Path,
    cam1: CameraIntrinsics,
    cam2: CameraIntrinsics,
    camera_distance_m: float,
) -> tuple[np.ndarray, np.ndarray, int, float, float | None]:
    """Relative pose of camera_2 in camera_1's frame from person keypoints.

    Returns (rodrigues rotation, translation [m], n_points, mean reprojection
    error px, estimated standing height m or None)."""
    pts1, pts2 = _load_keypoint_correspondences(pose_dir)
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

    # rough standing-height sanity figure: extent of the triangulated cloud
    extent = points3.max(axis=0) - points3.min(axis=0)
    height = float(np.max(extent)) if len(points3) > 50 else None

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
