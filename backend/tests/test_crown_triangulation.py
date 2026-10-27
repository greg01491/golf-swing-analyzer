import hashlib
import json

import cv2
import numpy as np
import pytest
import rtoml

from golf_sim.config import CalibrationValidationConfig
from golf_sim.diagnostics.crown_triangulation import (
    pair_native_track_frames,
    run_crown_triangulation_diagnostic,
    triangulate_crown_observations,
)
from golf_sim.diagnostics.print_calibration_board import build_pdf
from golf_sim.diagnostics.shared_board_geometry import evaluate_shared_board_placements


def _known_cameras():
    matrix = np.array([[900, 0, 640], [0, 880, 360], [0, 0, 1]], dtype=float)
    return {
        "camera_1": {
            "matrix": matrix,
            "rotation": np.zeros(3),
            "translation": np.zeros(3),
            "distortions": np.array([0.1, -0.04, 0.002, -0.001]),
        },
        "camera_2": {
            "matrix": matrix,
            "rotation": np.array([0.02, 0.15, -0.03]),
            "translation": np.array([-0.8, 0, 0.1]),
            "distortions": np.array([-0.08, 0.03, -0.001, 0.002]),
        },
    }


def _project(points, camera):
    return cv2.projectPoints(
        points, camera["rotation"], camera["translation"], camera["matrix"], camera["distortions"]
    )[0].reshape(-1, 2)


def test_distorted_camera_triangulation_recovers_known_geometry_without_filling_missing():
    calibration = _known_cameras()
    points = np.array([[0.2, -0.4, 3], [-0.1, -0.5, 3.2], [0.4, 0.2, 2.8]], dtype=float)
    first = _project(points, calibration["camera_1"])
    second = _project(points, calibration["camera_2"])
    second[1] = np.nan
    result = triangulate_crown_observations(
        first, second, calibration, CalibrationValidationConfig()
    )
    np.testing.assert_allclose(result["accepted_world_xyz_m"][[0, 2]], points[[0, 2]], atol=1e-6)
    assert np.isnan(result["accepted_world_xyz_m"][1]).all()
    assert result["accepted"].tolist() == [True, False, True]
    assert np.max(result["errors_px"][[0, 2]]) < 1e-5


def test_bad_correspondences_and_negative_depth_never_become_accepted_points():
    calibration = _known_cameras()
    points = np.array([[0.2, -0.4, 3], [0.1, -0.3, -3]], dtype=float)
    first = _project(points, calibration["camera_1"])
    second = _project(points, calibration["camera_2"])
    second[0, 1] += 100
    result = triangulate_crown_observations(
        first, second, calibration, CalibrationValidationConfig()
    )
    assert not result["within_reprojection_limit"][0]
    assert not result["positive_depth"][1]
    assert not result["accepted"].any()
    assert np.isnan(result["accepted_world_xyz_m"]).all()


def test_native_time_pairing_does_not_hold_or_guess_different_rate_frames():
    first = {
        "summary": {"fps": 120},
        "frames": [{"frame_index": index, "time_s": index / 120} for index in range(5)],
    }
    second = {
        "summary": {"fps": 60},
        "frames": [{"frame_index": index, "time_s": index / 60} for index in range(3)],
    }
    pairs = pair_native_track_frames(first, second)
    assert [
        (a["frame_index"] if a else None, b["frame_index"] if b else None) for a, b in pairs
    ] == [(0, 0), (1, None), (2, 1), (3, None), (4, 2)]
    second["frames"][1]["time_s"] = 0
    with pytest.raises(ValueError, match="timestamp"):
        pair_native_track_frames(first, second)


def test_isolated_report_preserves_missing_frames_and_never_certifies_metrics(tmp_path):
    source = tmp_path / "session"
    (source / "pose2sim/calibration").mkdir(parents=True)
    calibration = _known_cameras()
    for camera in calibration.values():
        camera["size"] = [1280, 720]
        camera["fisheye"] = False
    serial = {
        role: {
            key: value.tolist() if isinstance(value, np.ndarray) else value
            for key, value in camera.items()
        }
        for role, camera in calibration.items()
    }
    (source / "pose2sim/calibration/Calib_rig.toml").write_text(rtoml.dumps(serial))
    (source / "metadata.json").write_text(
        json.dumps(
            {"cameras": {role: {"width": 1280, "height": 720, "fps": 120} for role in calibration}}
        )
    )
    points = np.array([[0.2, -0.4, 3]] * 4, dtype=float)
    tracks = []
    for role, camera in calibration.items():
        video = source / f"{role}.mp4"
        video.write_bytes(role.encode())
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        pixels = _project(points, camera)
        frames = [
            {
                "frame_index": frame,
                "time_s": frame / 120,
                "status": "image_consistent",
                "candidate_xy": pixels[frame].tolist(),
                "raw_xy": pixels[frame].tolist(),
            }
            for frame in range(4)
        ]
        frames[0].update(status="operator_seed_recorded", candidate_xy=None)
        if role == "camera_2":
            frames[2].update(status="awaiting_operator_seed", candidate_xy=None)
        path = tmp_path / role / "comparison.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                {
                    "summary": {
                        "diagnostic_only": True,
                        "tracking_policy": "operator_seed_independent_image_motion",
                        "fps": 120,
                        "frame_count": 4,
                        "source_video": str(video),
                        "source_sha256": {str(video): digest},
                    },
                    "frames": frames,
                }
            )
        )
        tracks.append(path)
    before = {path: path.read_bytes() for path in source.rglob("*") if path.is_file()}
    output = tmp_path / "triangulation"
    summary = run_crown_triangulation_diagnostic(
        source, *tracks, output, CalibrationValidationConfig()
    )
    assert summary["tracked"]["paired_observations"] == 2
    assert summary["tracked"]["pixel_and_depth_gate_passes"] == 2
    assert summary["missing_or_unmatched_pairs"] == 2
    assert summary["eligible_for_metrics"] is False
    assert summary["exposure_synchronization_verified"] is False
    records = json.loads((output / "triangulation.json").read_text())["frames"]
    assert records[0]["gate_passed_world_xyz_m"] == [None, None, None]
    assert records[2]["gate_passed_world_xyz_m"] == [None, None, None]
    np.testing.assert_allclose(records[1]["gate_passed_world_xyz_m"], points[1], atol=1e-5)
    assert {path: path.read_bytes() for path in before} == before
    with pytest.raises(ValueError, match="outside"):
        run_crown_triangulation_diagnostic(
            source, *tracks, source / "unsafe", CalibrationValidationConfig()
        )
    with pytest.raises(FileExistsError):
        run_crown_triangulation_diagnostic(source, *tracks, output, CalibrationValidationConfig())
    payload = json.loads(tracks[0].read_text())
    payload["summary"]["source_sha256"][str(source / "camera_1.mp4")] = "0" * 64
    tracks[0].write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="selected session"):
        run_crown_triangulation_diagnostic(
            source, *tracks, tmp_path / "tampered", CalibrationValidationConfig()
        )
    assert not (tmp_path / "tampered").exists()


def test_tiled_checkerboard_pdf_has_eight_a4_landscape_pages_and_rejects_oversize(tmp_path):
    output = tmp_path / "checkerboard.pdf"
    build_pdf(output, 80)
    content = output.read_bytes()
    assert content.startswith(b"%PDF-1.4")
    assert content.count(b"/Type /Page /Parent") == 8
    assert content.count(b"/MediaBox [0 0 841.8898 595.2756]") == 8
    assert b"80 mm squares" in content
    assert b"[2 2] 0 d" in content
    with pytest.raises(ValueError, match="does not fit"):
        build_pdf(tmp_path / "too-large.pdf", 120)
    assert not (tmp_path / "too-large.pdf").exists()


def test_shared_board_pose_uses_whole_heldout_placements_and_both_projection_directions():
    calibration = _known_cameras()
    truth_rotation = np.array([0.03, 0.12, -0.02])
    rotation_matrix = cv2.Rodrigues(truth_rotation)[0]
    truth_translation = np.array([-0.8, 0.03, 0.12])
    calibration["camera_2"]["rotation"] = truth_rotation
    calibration["camera_2"]["translation"] = truth_translation
    object_points = np.zeros((28, 3), dtype=np.float32)
    object_points[:, :2] = np.mgrid[0:4, 0:7].T.reshape(-1, 2) * 0.0784
    placements = []
    for index in range(10):
        angle = np.array([0.025 * index, -0.04 + 0.01 * index, 0.02 * np.sin(index)])
        board_rotation = cv2.Rodrigues(angle)[0]
        board_translation = np.array(
            [-0.6 + 0.12 * index, -0.3 + 0.05 * (index % 3), 2.4 + 0.07 * index]
        )
        points_camera_1 = object_points @ board_rotation.T + board_translation
        points_camera_2 = points_camera_1 @ rotation_matrix.T + truth_translation
        first, _ = cv2.projectPoints(
            points_camera_1,
            np.zeros(3),
            np.zeros(3),
            calibration["camera_1"]["matrix"],
            calibration["camera_1"]["distortions"],
        )
        second, _ = cv2.projectPoints(
            points_camera_2,
            np.zeros(3),
            np.zeros(3),
            calibration["camera_2"]["matrix"],
            calibration["camera_2"]["distortions"],
        )
        placements.append(
            {
                "id": f"placement-{index}",
                "camera_1": first.reshape(-1, 2),
                "camera_2": second.reshape(-1, 2),
            }
        )

    result = evaluate_shared_board_placements(
        placements,
        calibration,
        square_size_m=0.0784,
        measured_baseline_m=float(np.linalg.norm(truth_translation)),
        fit_count=6,
        max_baseline_relative_error=0.05,
    )

    assert result["fit_placements"] == [f"placement-{index}" for index in range(6)]
    assert result["heldout_placements"] == [f"placement-{index}" for index in range(6, 10)]
    assert result["fitted_baseline_m"] == pytest.approx(np.linalg.norm(truth_translation), abs=1e-4)
    assert result["fitted_rotation_delta_from_active_deg"] == pytest.approx(0, abs=1e-3)
    np.testing.assert_allclose(
        result["diagnostic_pose"]["camera_2_rotation_rodrigues"], truth_rotation, atol=1e-5
    )
    np.testing.assert_allclose(
        result["diagnostic_pose"]["camera_2_translation_m"], truth_translation, atol=1e-5
    )
    assert result["heldout_camera_1_to_camera_2"]["p95_px"] < 1e-3
    assert result["heldout_camera_2_to_camera_1"]["p95_px"] < 1e-3
    assert result["active_heldout_camera_1_to_camera_2"]["p95_px"] < 1e-3
    assert result["active_heldout_camera_2_to_camera_1"]["p95_px"] < 1e-3
    assert result["active_best_order_heldout_camera_1_to_camera_2"]["p95_px"] < 1e-3
    assert result["active_best_order_heldout_camera_2_to_camera_1"]["p95_px"] < 1e-3
    assert result["candidate_for_activation"] is False
    assert result["timing_verified"] is False
