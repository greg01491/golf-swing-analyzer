"""Validates the essential-matrix extrinsic recovery against synthetic
cameras with known ground-truth geometry."""

import json
from pathlib import Path

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


def _synthetic_skeleton(n_frames=100, height_m=1.88, seed=3):
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

    _, _, _, _, height = calibrate_extrinsics(
        tmp_path, cam1, cam2, camera_distance_m=2.5, frame_rate_hz=60
    )

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

    assert (
        rig_calibration._estimate_standing_height(pts3, np.zeros(len(pts3)), np.arange(len(pts3)))
        is None
    )
    with pytest.raises(CalibrationDataError, match="held-out"):
        calibrate_extrinsics(tmp_path, cam1, cam2, camera_distance_m=2.5, frame_rate_hz=60)


def test_extrinsics_recover_known_camera_geometry(monkeypatch, tmp_path):
    cam1, cam2 = _intr(), _intr(f=850.0)
    # ground truth: camera 2 is 2.5m away, rotated 80 degrees about vertical
    angle = np.radians(80)
    R_true = cv2.Rodrigues(np.array([0.0, angle, 0.0]))[0]
    t_dir = np.array([-0.85, 0.05, 0.52])
    t_true = t_dir / np.linalg.norm(t_dir) * 2.5

    correspondences = _skeleton_correspondences(_synthetic_skeleton(), cam1, cam2, R_true, t_true)

    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda pose_dir, confidence_threshold=0.6: correspondences,
    )

    rot, trans, n_points, err, height = calibrate_extrinsics(
        tmp_path, cam1, cam2, camera_distance_m=2.5, frame_rate_hz=60
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


def test_correspondences_match_frame_identity_when_one_camera_drops_a_file(tmp_path):
    for role, frames in (("camera_1", (0, 1, 2)), ("camera_2", (0, 2))):
        directory = tmp_path / f"{role}_json"
        directory.mkdir()
        for frame in frames:
            keypoints = np.ones((26, 3))
            keypoints[:, 0] = frame * 10
            payload = {"people": [{"pose_keypoints_2d": keypoints.ravel().tolist()}]}
            (directory / f"{role}_{frame:06d}.json").write_text(json.dumps(payload))

    first, second, frame_ids, _ = rig_calibration._load_keypoint_correspondences(tmp_path)

    assert set(frame_ids) == {0, 2}
    assert np.array_equal(first[:, 0], second[:, 0])


def test_good_fitting_inliers_cannot_hide_bad_heldout_geometry(monkeypatch, tmp_path):
    cam1, cam2 = _intr(), _intr(f=850)
    rotation = cv2.Rodrigues(np.array([0.0, np.radians(80), 0.0]))[0]
    translation = np.array([-0.85, 0.05, 0.52])
    translation = translation / np.linalg.norm(translation) * 2.5
    first, second, frame_ids, joint_ids = _skeleton_correspondences(
        _synthetic_skeleton(n_frames=100), cam1, cam2, rotation, translation
    )
    second[frame_ids >= 75, 1] += 80
    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda *args, **kwargs: (first, second, frame_ids, joint_ids),
    )

    with pytest.raises(CalibrationDataError, match="held-out"):
        calibrate_extrinsics(tmp_path, cam1, cam2, camera_distance_m=2.5, frame_rate_hz=60)


def test_failed_bundle_cannot_replace_active_calibration(tmp_path):
    from golf_sim.pose.calibration_bundle import load_active_bundle, publish_bundle

    calibration = tmp_path / "candidate.toml"
    calibration.write_text("camera evidence")
    publish_bundle(tmp_path, calibration, {"status": "accepted"}, {})
    before = (tmp_path / "active.json").read_bytes()
    with pytest.raises(ValueError, match="independently accepted"):
        publish_bundle(tmp_path, calibration, {"status": "failed"}, {})
    assert (tmp_path / "active.json").read_bytes() == before
    assert load_active_bundle(tmp_path)["validation"]["status"] == "accepted"


def test_interrupted_activation_preserves_previous_bundle(tmp_path, monkeypatch):
    from golf_sim.pose import calibration_bundle

    candidate = tmp_path / "candidate.toml"
    candidate.write_text("first geometry")
    calibration_bundle.publish_bundle(tmp_path, candidate, {"status": "accepted"}, {})
    previous = (tmp_path / "active.json").read_bytes()
    candidate.write_text("new geometry")
    replace = calibration_bundle.os.replace

    def fail_pointer(source, target):
        if Path(target).name == "active.json":
            raise OSError("interrupted activation")
        return replace(source, target)

    monkeypatch.setattr(calibration_bundle.os, "replace", fail_pointer)
    with pytest.raises(OSError, match="interrupted activation"):
        calibration_bundle.publish_bundle(tmp_path, candidate, {"status": "accepted"}, {})
    assert (tmp_path / "active.json").read_bytes() == previous


def test_camera_validation_cancellation_does_not_activate_a_candidate(tmp_path):
    from golf_sim.config import load_config
    from golf_sim.pose.wizard import compute_rig_calibration

    config = load_config()
    with pytest.raises(CalibrationDataError, match="cancelled"):
        compute_rig_calibration(tmp_path, config, 2.5, cancelled=lambda: True)


def test_wizard_heldout_failure_preserves_previous_calibration(tmp_path, monkeypatch):
    from golf_sim.config import load_config
    from golf_sim.pose import estimate, wizard

    config = load_config().model_copy(deep=True)
    config.calibration.dir = str(tmp_path / "rig")
    calibration_root = tmp_path / "rig"
    calibration_root.mkdir()
    previous = calibration_root / "Calib_rig.toml"
    previous.write_text("previous accepted geometry")
    shots = [{"id": "lens", "kind": "intrinsics"}, {"id": "position", "kind": "extrinsics"}]
    for shot in shots:
        directory = tmp_path / "sessions" / shot["id"]
        directory.mkdir(parents=True)
        for camera in config.cameras.devices:
            (directory / f"{camera.role}.mp4").write_bytes(b"fixture")
        (directory / "metadata.json").write_text(
            json.dumps(
                {
                    "cameras": {
                        camera.role: {
                            "fps": camera.fps,
                            "width": camera.width,
                            "height": camera.height,
                        }
                        for camera in config.cameras.devices
                    }
                }
            )
        )
    monkeypatch.setattr(wizard, "list_calibration_shots", lambda *_: shots)
    monkeypatch.setattr(wizard, "calibrate_intrinsics", lambda *args, **kwargs: _intr())
    monkeypatch.setattr(estimate, "run_pose_estimation", lambda *args: None)

    def fail_validation(*args, **kwargs):
        raise CalibrationDataError("held-out camera_2 shoulder coverage failed")

    monkeypatch.setattr(wizard, "calibrate_extrinsics", fail_validation)
    with pytest.raises(CalibrationDataError, match="held-out"):
        wizard.compute_rig_calibration(tmp_path, config, 2.5)
    assert previous.read_text() == "previous accepted geometry"
    assert not (calibration_root / "active.json").exists()


def test_capture_mode_difference_is_incompatible_not_proof_of_movement():
    from golf_sim.pose.calibration_bundle import compare_signatures

    original = {
        "camera_1": {
            "identity": "fixed-device",
            "width": 1280,
            "height": 720,
            "rotation_deg": 0,
            "requested_fps": 60,
            "autofocus": False,
            "focus": 0,
        }
    }
    changed = {
        "camera_1": {**original["camera_1"], "requested_fps": 120, "source_effective_fps": 110}
    }
    assert compare_signatures(original, changed)["status"] == "incompatible"
    assert all("moved" not in reason for reason in compare_signatures(original, changed)["reasons"])


def test_legacy_capture_does_not_inherit_current_camera_geometry():
    from golf_sim.config import load_config
    from golf_sim.pose.calibration_bundle import camera_signatures, compare_signatures

    config = load_config()
    metadata = {"cameras": {"camera_1": {"width": 1280, "height": 720, "fps": 60}}}
    signatures = camera_signatures(config, metadata)
    assert signatures["camera_1"]["identity"] is None
    assert signatures["camera_1"]["rotation_deg"] is None
    assert signatures["camera_1"]["focus"] is None
    assert compare_signatures(signatures, signatures)["status"] == "unverified"


@pytest.mark.parametrize(
    "field,value",
    [
        ("min_coverage", 1.1),
        ("max_normal_difference_deg", 90),
        ("partition_gap_s", -1),
        ("min_board_span_px", 0),
    ],
)
def test_validation_settings_reject_invalid_limits(field, value):
    from golf_sim.config import CalibrationValidationConfig

    with pytest.raises(ValueError):
        CalibrationValidationConfig(**{field: value})


def test_lens_validation_requires_independent_capture_group(monkeypatch, tmp_path):
    from golf_sim.config import CalibrationValidationConfig

    views, _, _ = _synthetic_board_views(n_good=30, n_bad=0)
    _patch_corners(monkeypatch, views)
    with pytest.raises(CalibrationDataError, match="independent capture"):
        calibrate_intrinsics(
            [tmp_path / "one.mp4"], _BOARD, _SQUARE_MM, validation=CalibrationValidationConfig()
        )


def test_lens_validation_reserves_whole_clips_before_fitting(monkeypatch, tmp_path):
    from golf_sim.config import CalibrationValidationConfig

    views, _, _ = _synthetic_board_views(n_good=36, n_bad=0)
    clips = [tmp_path / f"view_{index}.mp4" for index in range(3)]
    by_clip = {clip: views[index * 12 : (index + 1) * 12] for index, clip in enumerate(clips)}
    monkeypatch.setattr(rig_calibration, "find_board_corners", lambda clip, _: iter(by_clip[clip]))
    result = calibrate_intrinsics(
        clips, _BOARD, _SQUARE_MM, validation=CalibrationValidationConfig()
    )
    assert result.validation["status"] == "accepted"
    assert result.validation["fit_views"] == 24
    assert result.validation["heldout_views"] == 12
    assert result.validation["heldout_captures"] == [str(clips[-1])]


def test_missing_body_region_fails_even_when_visible_points_fit(monkeypatch, tmp_path):
    cam1, cam2 = _intr(), _intr(f=850)
    rotation = cv2.Rodrigues(np.array([0.0, np.radians(80), 0.0]))[0]
    translation = np.array([-0.85, 0.05, 0.52])
    translation = translation / np.linalg.norm(translation) * 2.5
    first, second, frame_ids, joint_ids = _skeleton_correspondences(
        _synthetic_skeleton(), cam1, cam2, rotation, translation
    )
    included = ~((frame_ids >= 75) & np.isin(joint_ids, [5, 6]))
    monkeypatch.setattr(
        rig_calibration,
        "_load_keypoint_correspondences",
        lambda *args: (first[included], second[included], frame_ids[included], joint_ids[included]),
    )
    with pytest.raises(CalibrationDataError, match="shoulders coverage"):
        calibrate_extrinsics(tmp_path, cam1, cam2, 2.5, frame_rate_hz=60)


def test_negative_depth_camera_geometry_is_rejected():
    from golf_sim.config import CalibrationValidationConfig

    camera = _intr()
    points = np.tile(np.array([0.2, 0.1, 3.0]), (26, 1))
    translation = np.array([-2.5, 0.0, 0.0])
    first, _ = cv2.projectPoints(
        points, np.zeros(3), np.zeros(3), camera.matrix, camera.distortions
    )
    second, _ = cv2.projectPoints(
        points, np.zeros(3), translation, camera.matrix, camera.distortions
    )
    report = rig_calibration.evaluate_camera_geometry(
        first.reshape(-1, 2),
        second.reshape(-1, 2),
        np.arange(26),
        camera,
        camera,
        np.zeros(3),
        -translation,
        CalibrationValidationConfig(),
    )
    assert report["status"] == "failed"
    assert report["positive_depth_coverage"] == 0


def test_ground_reference_uses_independent_measured_board_placements():
    from golf_sim.config import CalibrationValidationConfig
    from golf_sim.pose.ground_reference import solve_ground_reference

    camera = _intr()
    shift = np.array([-1.5, 0.0, 0.0])
    calibration = {
        role: {
            "matrix": camera.matrix.tolist(),
            "distortions": [-0.2, 0.05, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "translation": translation.tolist(),
        }
        for role, translation in (("camera_1", np.zeros(3)), ("camera_2", shift))
    }
    grid = np.zeros((28, 3))
    grid[:, :2] = np.mgrid[0:4, 0:7].T.reshape(-1, 2) * 0.06
    observations = []
    for capture in ("first", "repeat"):
        points = grid + np.array([0.0, 0.0 if capture == "first" else 0.1, 2.4])
        for frame in range(6):
            observation = {"capture": capture, "frame": frame}
            for role in calibration:
                projected, _ = cv2.projectPoints(
                    points,
                    np.zeros(3),
                    np.asarray(calibration[role]["translation"]),
                    camera.matrix,
                    np.asarray(calibration[role]["distortions"]),
                )
                observation[role] = projected.reshape(-1, 2)
            observations.append(observation)
    settings = CalibrationValidationConfig()
    reference = solve_ground_reference(calibration, observations, _BOARD, 0.06, 1, settings)
    assert reference["status"] == "accepted"
    assert reference["up"] == pytest.approx([0, 0, -1], abs=0.0001)
    assert reference["target"] == pytest.approx([1, 0, 0], abs=0.0001)
    assert reference["ball"] == pytest.approx([0, -1, 0], abs=0.0001)
    basis = np.array([reference["up"], reference["target"], reference["ball"]])
    assert basis @ basis.T == pytest.approx(np.eye(3), abs=1e-9)
    assert reference["heldout_captures"] == ["repeat"]
    with pytest.raises(CalibrationDataError, match="measured board lengths"):
        solve_ground_reference(calibration, observations, _BOARD, 0.03, 1, settings)
    with pytest.raises(CalibrationDataError, match="two independent"):
        solve_ground_reference(calibration, observations[:6], _BOARD, 0.06, 1, settings)


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
