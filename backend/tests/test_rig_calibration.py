"""Validates the essential-matrix extrinsic recovery against synthetic
cameras with known ground-truth geometry."""

import cv2
import numpy as np
import pytest

from golf_sim.pose import rig_calibration
from golf_sim.pose.rig_calibration import (
    CalibrationDataError,
    CameraIntrinsics,
    RigCalibration,
    calibrate_extrinsics,
    calibrate_intrinsics,
    write_calib_toml,
)


def _intr(f=900.0, w=1280, h=720):
    K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])
    return CameraIntrinsics(
        matrix=K, distortions=np.zeros(4), size=(w, h), rms_error=0.2, n_views=10
    )


def _synthetic_scene(n=600, seed=7):
    """Person-ish 3D point cloud ~3m in front of camera 1."""
    rng = np.random.default_rng(seed)
    pts = np.column_stack(
        [
            rng.uniform(-0.8, 0.8, n),  # x: arm sweep
            rng.uniform(-0.9, 0.9, n),  # y: height range
            rng.uniform(2.4, 3.4, n),  # z: depth in front of cam1
        ]
    )
    return pts


def _synthetic_skeleton(n_frames=40, height_m=1.88, seed=3):
    """HALPE_26 skeletons over several frames, with a known head-to-feet size.

    Head sits at +height/2 and every foot joint at -height/2, so the true
    standing height is exactly ``height_m``. The golfer drifts and sweeps their
    arms between frames, which is what made the old bounding-box estimate read
    high."""
    rng = np.random.default_rng(seed)
    h = height_m
    base = np.zeros((26, 3))
    base[17] = [0.0, h / 2, 0.0]  # Head
    base[0] = [0.0, h / 2 - 0.12, 0.05]  # Nose
    base[18] = [0.0, h / 2 - 0.25, 0.0]  # Neck
    base[5], base[6] = [0.21, h / 2 - 0.28, 0.0], [-0.21, h / 2 - 0.28, 0.0]  # shoulders
    base[7], base[8] = [0.28, h / 2 - 0.58, 0.0], [-0.28, h / 2 - 0.58, 0.0]  # elbows
    base[9], base[10] = [0.30, h / 2 - 0.86, 0.1], [-0.30, h / 2 - 0.86, 0.1]  # wrists
    base[19] = [0.0, 0.0, 0.0]  # Hip
    base[11], base[12] = [0.16, 0.0, 0.0], [-0.16, 0.0, 0.0]  # hips
    base[13], base[14] = [0.17, -0.46, 0.0], [-0.17, -0.46, 0.0]  # knees
    for j in (15, 24):  # left ankle, left heel
        base[j] = [0.16, -h / 2, 0.0]
    for j in (16, 25):  # right ankle, right heel
        base[j] = [-0.16, -h / 2, 0.0]

    frames = []
    for _ in range(n_frames):
        pose = base.copy()
        # arms sweep through the swing; nothing else changes length
        swing = rng.uniform(-0.5, 0.5)
        for j in (7, 8, 9, 10):
            pose[j, 0] += swing * 0.6
            pose[j, 2] += swing * 0.5
        pose += rng.normal(0.0, 0.01, pose.shape)  # detection noise
        pose += np.array([rng.uniform(-0.15, 0.15), 0.0, rng.uniform(2.6, 3.2)])
        frames.append(pose)
    return frames


def _skeleton_correspondences(frames, cam1, cam2, R_true, t_true):
    """Projects skeleton frames into both cameras, in loader output form."""
    pts1, pts2, frame_ids, joint_ids = [], [], [], []
    for frame_no, pose in enumerate(frames):
        p1, _ = cv2.projectPoints(pose, np.zeros(3), np.zeros(3), cam1.matrix, cam1.distortions)
        p2, _ = cv2.projectPoints(
            pose, cv2.Rodrigues(R_true)[0], t_true, cam2.matrix, cam2.distortions
        )
        pts1.append(p1.reshape(-1, 2))
        pts2.append(p2.reshape(-1, 2))
        frame_ids.append(np.full(len(pose), frame_no))
        joint_ids.append(np.arange(len(pose)))
    return (
        np.vstack(pts1),
        np.vstack(pts2),
        np.concatenate(frame_ids),
        np.concatenate(joint_ids),
    )


def test_estimated_height_measures_the_person_not_the_swept_volume(monkeypatch, tmp_path):
    """A bounding box over every frame reads far too tall, because it spans the
    arc the arms travel through and the golfer's drift, not the golfer."""
    cam1, cam2 = _intr(), _intr(f=850.0)
    R_true = cv2.Rodrigues(np.array([0.0, np.radians(80), 0.0]))[0]
    t_dir = np.array([-0.85, 0.05, 0.52])
    t_true = t_dir / np.linalg.norm(t_dir) * 2.5

    frames = _synthetic_skeleton(height_m=1.88)
    corr = _skeleton_correspondences(frames, cam1, cam2, R_true, t_true)
    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda pose_dir, confidence_threshold=0.6: corr,
    )

    _, _, _, _, height = calibrate_extrinsics(tmp_path, cam1, cam2, camera_distance_m=2.5)

    assert height is not None
    assert abs(height - 1.88) < 0.06, f"expected ~1.88m, got {height:.3f}m"


def test_estimated_height_is_none_for_an_unknown_skeleton(monkeypatch, tmp_path):
    """Anonymous point clouds have no head or feet, so we must not guess."""
    cam1, cam2 = _intr(), _intr(f=850.0)
    pts3 = _synthetic_scene()
    proj1, _ = cv2.projectPoints(pts3, np.zeros(3), np.zeros(3), cam1.matrix, cam1.distortions)
    R_true = cv2.Rodrigues(np.array([0.0, np.radians(80), 0.0]))[0]
    t_true = np.array([-0.85, 0.05, 0.52])
    t_true = t_true / np.linalg.norm(t_true) * 2.5
    proj2, _ = cv2.projectPoints(
        pts3, cv2.Rodrigues(R_true)[0], t_true, cam2.matrix, cam2.distortions
    )
    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda pose_dir, confidence_threshold=0.6: (
            proj1.reshape(-1, 2),
            proj2.reshape(-1, 2),
            np.zeros(len(pts3), dtype=int),
            np.arange(len(pts3)),  # far more "joints" than HALPE_26
        ),
    )

    _, _, _, _, height = calibrate_extrinsics(tmp_path, cam1, cam2, camera_distance_m=2.5)
    assert height is None


def test_extrinsics_recover_known_camera_geometry(monkeypatch, tmp_path):
    cam1, cam2 = _intr(), _intr(f=850.0)
    # ground truth: camera 2 is 2.5m away, rotated 80 degrees about vertical
    angle = np.radians(80)
    R_true = cv2.Rodrigues(np.array([0.0, angle, 0.0]))[0]
    t_dir = np.array([-0.85, 0.05, 0.52])
    t_true = t_dir / np.linalg.norm(t_dir) * 2.5

    pts3 = _synthetic_scene()
    proj1, _ = cv2.projectPoints(pts3, np.zeros(3), np.zeros(3), cam1.matrix, cam1.distortions)
    proj2, _ = cv2.projectPoints(
        pts3, cv2.Rodrigues(R_true)[0], t_true, cam2.matrix, cam2.distortions
    )

    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda pose_dir, confidence_threshold=0.6: (
            proj1.reshape(-1, 2),
            proj2.reshape(-1, 2),
            np.zeros(len(pts3), dtype=int),
            np.arange(len(pts3)),
        ),
    )

    rot, trans, n_points, err, height = calibrate_extrinsics(
        tmp_path, cam1, cam2, camera_distance_m=2.5
    )

    R_est = cv2.Rodrigues(rot)[0]
    rotation_diff_deg = np.degrees(np.arccos(np.clip((np.trace(R_est @ R_true.T) - 1) / 2, -1, 1)))
    assert rotation_diff_deg < 1.0
    assert np.linalg.norm(trans - t_true) < 0.05  # within 5cm
    assert n_points > 400
    assert err < 2.0  # px


def test_extrinsics_reject_too_few_points(monkeypatch, tmp_path):
    cam = _intr()
    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda pose_dir, confidence_threshold=0.6: (
            np.zeros((10, 2)),
            np.zeros((10, 2)),
            np.zeros(10, dtype=int),
            np.arange(10),
        ),
    )
    with pytest.raises(CalibrationDataError, match="correspondences"):
        calibrate_extrinsics(tmp_path, cam, cam, camera_distance_m=2.5)


def test_intrinsics_reject_insufficient_views(tmp_path):
    empty_clip = tmp_path / "camera_1.mp4"
    empty_clip.write_bytes(b"")
    with pytest.raises(CalibrationDataError, match="board views"):
        calibrate_intrinsics([empty_clip], (4, 7), 28.4)


def test_write_calib_toml_is_readable_by_pose2sim_convention(tmp_path):
    import rtoml

    rig = RigCalibration(
        cam1=_intr(),
        cam2=_intr(f=850.0),
        rotation_cam2=np.array([0.1, 1.2, -0.05]),
        translation_cam2=np.array([-2.1, 0.1, 1.3]),
        n_correspondences=1234,
        mean_reprojection_error_px=1.1,
        estimated_person_height_m=1.8,
    )
    out = tmp_path / "Calib_rig.toml"
    write_calib_toml(out, rig)

    calib = rtoml.load(out)
    cams = [k for k in calib if k != "metadata"]
    assert cams == ["camera_1", "camera_2"]
    for cam in cams:
        assert np.array(calib[cam]["matrix"]).shape == (3, 3)
        assert len(calib[cam]["distortions"]) == 4
        assert len(calib[cam]["rotation"]) == 3
        assert len(calib[cam]["translation"]) == 3
    assert calib["camera_1"]["rotation"] == [0.0, 0.0, 0.0]
    assert calib["metadata"]["n_correspondences"] == 1234


# --- intrinsics fitting -------------------------------------------------


_BOARD = (4, 7)
_SQUARE_MM = 28.4


def _board_object_points():
    rows, cols = _BOARD
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:rows, 0:cols].T.reshape(-1, 2) * _SQUARE_MM / 1000.0
    return objp


def _synthetic_board_views(n_good=30, n_bad=6, seed=11, k3=0.0):
    """Board views from a known wide-angle lens, plus a few 'blurred' ones.

    Mirrors the live rig: most views are clean, a handful are badly off.
    """
    rng = np.random.default_rng(seed)
    w, h = 720, 1280
    K = np.array([[520.0, 0, w / 2], [0, 520.0, h / 2], [0, 0, 1.0]])
    dist = np.array([-0.41, 0.21, 0.0022, 0.00016, k3])
    objp = _board_object_points()

    views = []
    for i in range(n_good + n_bad):
        rvec = rng.uniform(-0.45, 0.45, 3)
        tvec = np.array(
            [rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), rng.uniform(0.35, 0.6)]
        )
        projected, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
        corners = projected.reshape(-1, 1, 2).astype(np.float32)
        if i >= n_good:  # motion-blurred / mis-localised corners
            corners = corners + rng.normal(0, 6.0, corners.shape).astype(np.float32)
        views.append((corners, (w, h)))
    return views, K, dist


def _patch_corners(monkeypatch, views):
    def fake_find(clip, corners_nb):
        yield from views

    monkeypatch.setattr(rig_calibration, "find_board_corners", fake_find)


def test_intrinsics_reject_outlier_views_instead_of_failing(monkeypatch, tmp_path):
    """Regression: 12 bad views out of 191 dragged the live rig's wide camera
    to 7.1px and tripped the 'lens calibration is poor' guard, even though the
    other 179 fitted to 0.48px. Bad views must be dropped, not fatal."""
    views, _, _ = _synthetic_board_views()
    _patch_corners(monkeypatch, views)

    result = calibrate_intrinsics([tmp_path / "camera_2.mp4"], _BOARD, _SQUARE_MM)

    assert result.rms_error < 1.0, f"outliers still dominate the fit ({result.rms_error:.2f}px)"
    assert result.n_views < len(views), "no outlier views were dropped"
    assert result.n_views >= 30


def test_stored_distortions_are_the_model_that_was_fitted(monkeypatch, tmp_path):
    """Regression: the fit produced 5 coefficients but only 4 were stored, so
    the saved lens model was not the fitted one -- k3 was -63.6 on the live
    wide camera. The stored model must reproduce the board views."""
    views, _, _ = _synthetic_board_views(n_good=30, n_bad=0, k3=-3.0)
    _patch_corners(monkeypatch, views)

    result = calibrate_intrinsics([tmp_path / "camera_2.mp4"], _BOARD, _SQUARE_MM)

    assert len(result.distortions) == 4
    objp = _board_object_points()
    worst = 0.0
    for corners, _size in views:
        ok, rvec, tvec = cv2.solvePnP(objp, corners, result.matrix, result.distortions)
        assert ok
        projected, _ = cv2.projectPoints(objp, rvec, tvec, result.matrix, result.distortions)
        worst = max(
            worst, cv2.norm(corners, projected.reshape(corners.shape), cv2.NORM_L2) / len(objp)
        )
    assert worst < 1.0, f"stored intrinsics do not reproduce the views ({worst:.2f}px)"
