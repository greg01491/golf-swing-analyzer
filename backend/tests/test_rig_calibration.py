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
    assert height is not None and 1.5 < height < 2.2  # y-range ~1.8m dominates


def test_extrinsics_reject_too_few_points(monkeypatch, tmp_path):
    cam = _intr()
    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda pose_dir, confidence_threshold=0.6: (np.zeros((10, 2)), np.zeros((10, 2))),
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
