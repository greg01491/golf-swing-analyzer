import hashlib
import json

import cv2
import numpy as np
import pytest

from golf_sim.config import load_config
from golf_sim.pose.calibration_bundle import (
    atomic_json,
    camera_signatures,
    fingerprint,
    publish_bundle,
)
from golf_sim.pose.reconstruction_evidence import (
    MARKER_INDICES,
    WORLD_TO_TRC,
    load_ground_evidence,
    review_camera_tolerances,
    snapshot_bundle,
    verified_artifact_evidence,
    write_reconstruction_evidence,
)
from golf_sim.pose.rig_calibration import CameraIntrinsics, RigCalibration, write_calib_toml
from tests.test_analyze_p_positions import _write_trc


@pytest.fixture
def measured_session(tmp_path, synthetic_swing_full):
    config = load_config().model_copy(deep=True)
    config.calibration.dir = str(tmp_path / "rig")
    root = tmp_path / "rig"
    root.mkdir()
    directory = tmp_path / "session"
    directory.mkdir()
    cameras = {}
    for camera in config.cameras.devices:
        camera.name = f"stable-{camera.role}"
        camera.autofocus = False
        camera.focus = 0
        rotated = camera.rotation_deg in (90, 270)
        cameras[camera.role] = {
            "device_name": camera.name,
            "width": camera.height if rotated else camera.width,
            "height": camera.width if rotated else camera.height,
            "rotation_deg": camera.rotation_deg,
            "fps": camera.fps,
            "requested_fps": camera.fps,
            "geometry_controls": {"autofocus": {"readback": 0}, "focus": {"readback": 0}},
        }
    metadata = {"cameras": cameras}
    atomic_json(directory / "metadata.json", metadata)
    matrix = np.array([[900.0, 0, 640], [0, 900, 360], [0, 0, 1]])
    camera = CameraIntrinsics(matrix, np.zeros(4), (1280, 720), 0.1, 20)
    rig = RigCalibration(camera, camera, np.zeros(3), np.array([-0.5, 0.0, 0.0]), 1000, 0.1, 1.8)
    candidate = tmp_path / "candidate.toml"
    write_calib_toml(candidate, rig)
    bundle = publish_bundle(
        root, candidate, {"status": "accepted"}, camera_signatures(config, metadata)
    )
    ground = {
        "version": 1,
        "status": "accepted",
        "bundle_id": bundle["bundle_id"],
        "calibration_sha256": fingerprint(candidate),
        "up": [0, -1, 0],
        "target": [-1, 0, 0],
        "ball": [0, 0, 1],
    }
    identity = hashlib.sha256(
        json.dumps(ground, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    atomic_json(root / "references" / f"{identity}.json", ground)
    atomic_json(
        root / "active.json",
        {"version": 1, "bundle_id": bundle["bundle_id"], "ground_id": identity},
    )
    calibration = directory / "pose2sim" / "calibration"
    calibration.mkdir(parents=True)
    (calibration / "Calib_rig.toml").write_bytes(candidate.read_bytes())
    rotation = np.array([[1.0, 0, 0], [0, 0, -1], [0, 1, 0]])
    world = synthetic_swing_full.coords @ rotation.T + np.array([0.0, 1.5, 3.0])
    for camera_index, role in enumerate(("camera_1", "camera_2")):
        associated = directory / "pose2sim" / "pose-associated" / f"{role}_json"
        associated.mkdir(parents=True)
        shift = np.array([-0.5 * camera_index, 0.0, 0.0])
        projected, _ = cv2.projectPoints(
            world.reshape(-1, 3), np.zeros(3), shift, matrix, np.zeros(4)
        )
        projected = projected.reshape(synthetic_swing_full.n_frames, -1, 2)
        for frame in range(synthetic_swing_full.n_frames):
            points = np.zeros((26, 3))
            for name, index in MARKER_INDICES.items():
                if name in synthetic_swing_full.marker_names:
                    points[index, :2] = projected[
                        frame, synthetic_swing_full.marker_names.index(name)
                    ]
                    points[index, 2] = 1
            atomic_json(
                associated / f"{role}_{frame:06d}.json",
                {"people": [{"pose_keypoints_2d": points.ravel().tolist()}]},
            )
    synthetic_swing_full.coords = world @ WORLD_TO_TRC.T
    trc = directory / "pose2sim" / "pose-3d" / "measured_filt_butterworth.trc"
    trc.parent.mkdir()
    _write_trc(synthetic_swing_full, trc)
    snapshot = snapshot_bundle(directory, config)
    write_reconstruction_evidence(
        directory,
        config,
        snapshot,
        [trc],
        [True] * (synthetic_swing_full.n_frames * len(synthetic_swing_full.marker_names)),
    )
    return directory, config, trc, snapshot


def test_measured_ground_reaches_exact_filtered_artifact_with_supported_observations(
    measured_session,
):
    _, _, trc, snapshot = measured_session
    evidence = verified_artifact_evidence(trc)
    assert evidence["analysis_reference"]["bundle_id"] == snapshot["bundle_id"]
    assert evidence["analysis_reference"]["up"] == pytest.approx([-1, 0, 0])
    assert all(evidence["marker_support"]["LShoulder"])
    assert evidence["camera_coverage"]["camera_1"]["LShoulder"] == 1


def test_review_tolerance_only_flags_the_camera_and_frames_exceeding_the_gate(measured_session):
    directory, config, trc, _ = measured_session
    path = directory / "pose2sim" / "pose-associated" / "camera_1_json" / "camera_1_000040.json"
    payload = json.loads(path.read_text())
    limit = config.calibration.validation.max_tail_error_px
    payload["people"][0]["pose_keypoints_2d"][MARKER_INDICES["RHip"] * 3] += limit + 10
    atomic_json(path, payload)
    low_confidence = path.with_name("camera_1_000041.json")
    payload = json.loads(low_confidence.read_text())
    payload["people"][0]["pose_keypoints_2d"][MARKER_INDICES["RHip"] * 3 + 2] = 0.1
    atomic_json(low_confidence, payload)
    before = {file: file.read_bytes() for file in directory.rglob("*") if file.is_file()}
    issues = [
        {"marker": "RHip", "camera": role, "frame_indices": [40, 41, 42], "fps": 60}
        for role in ("camera_1", "camera_2")
    ]

    result = review_camera_tolerances(trc, config, issues)

    assert result["available"] is True
    assert set(result["failures"]) == {"camera_1/RHip/40", "camera_1/RHip/41"}
    failure = result["failures"]["camera_1/RHip/40"]
    assert failure["value"] == pytest.approx(limit + 10, abs=0.1)
    assert failure["threshold"] == limit
    assert failure["unit"] == "px"
    assert result["failures"]["camera_1/RHip/41"]["value"] == 0.1
    assert result["failures"]["camera_1/RHip/41"]["threshold"] == 0.3
    assert {file: file.read_bytes() for file in before} == before


def test_review_tolerance_without_bound_evidence_does_not_invent_failures(tmp_path):
    result = review_camera_tolerances(tmp_path / "unknown.trc", load_config(), [])
    assert result["available"] is False
    assert result["failures"] == {}


def test_tampered_reference_axes_cannot_authorize_measurement(measured_session):
    _, _, trc, _ = measured_session
    path = trc.with_suffix(".evidence.json")
    evidence = json.loads(path.read_text())
    evidence["analysis_reference"]["up"] = [0, 0, 1]
    atomic_json(path, evidence)
    with pytest.raises(ValueError, match="evidence"):
        verified_artifact_evidence(trc)


def test_raw_filtered_or_modified_file_cannot_reuse_old_reference_hash(measured_session):
    _, _, trc, _ = measured_session
    trc.write_text(trc.read_text() + "\n")
    with pytest.raises(ValueError, match="evidence"):
        verified_artifact_evidence(trc)


def test_parent_ground_fingerprint_is_verified(measured_session):
    _, config, _, snapshot = measured_session
    from pathlib import Path

    reference = load_ground_evidence(Path(config.calibration.dir), snapshot)
    assert reference["status"] == "accepted"
    path = Path(config.calibration.dir) / "references" / f"{snapshot['ground_id']}.json"
    reference["bundle_id"] = "unrelated-camera"
    atomic_json(path, reference)
    with pytest.raises(ValueError, match="fingerprint"):
        load_ground_evidence(Path(config.calibration.dir), snapshot)


def test_held_filled_coordinates_do_not_become_observed_measurements(measured_session):
    directory, config, trc, snapshot = measured_session
    from golf_sim.trc import read_trc

    sequence = read_trc(trc)
    support = np.ones((sequence.n_frames, len(sequence.marker_names)), dtype=bool)
    support[40:80, sequence.marker_names.index("LShoulder")] = False
    write_reconstruction_evidence(directory, config, snapshot, [trc], support.ravel().tolist())
    evidence = verified_artifact_evidence(trc)
    assert not any(evidence["marker_support"]["LShoulder"][40:80])
    assert evidence["observation_provenance"] == "pre_fill_triangulation"
    assert evidence["session_validation"]["status"] == "failed"
    assert evidence["session_validation"]["regions"]["shoulders"] < 0.8


def test_zero_filled_head_is_rejected_even_when_prefill_support_claims_observation(
    measured_session,
):
    from golf_sim.analysis.frame_of_reference import AnalysisReference
    from golf_sim.analysis.metrics import compute_metrics
    from golf_sim.analysis.phases import SwingPhases
    from golf_sim.trc import read_trc

    directory, config, trc, snapshot = measured_session
    sequence = read_trc(trc)
    sequence.coords[:, sequence.marker_names.index("Head")] = 0.0
    _write_trc(sequence, trc)
    write_reconstruction_evidence(
        directory,
        config,
        snapshot,
        [trc],
        [True] * (sequence.n_frames * len(sequence.marker_names)),
    )

    evidence = verified_artifact_evidence(trc)
    reference = evidence["analysis_reference"]
    analysis = compute_metrics(
        sequence,
        config.metrics,
        phases=SwingPhases(29, 89, 109),
        reference=AnalysisReference(
            up=np.asarray(reference["up"]),
            target=np.asarray(reference["target"]),
            ball=np.asarray(reference["ball"]),
            source=reference["source"],
        ),
        marker_support=evidence["marker_support"],
    )
    head_movement = next(metric for metric in analysis.metrics if metric.name == "head_movement_cm")

    assert not any(evidence["marker_support"]["Head"])
    assert evidence["session_validation"]["regions"]["head"] == 0
    assert head_movement.status == "unavailable"
    assert any("insufficient_coverage" in reason for reason in head_movement.reasons)


def test_what_if_metrics_mask_selected_observation_without_rewriting_session(
    measured_session,
):
    from golf_sim.analysis.cli import analyze_session_what_if

    directory, config, trc, _ = measured_session
    metadata_path = directory / "metadata.json"
    metadata_before = metadata_path.read_bytes()
    trc_before = trc.read_bytes()
    metrics_path = directory / "metrics.json"
    original_metrics = {"phases": {"address_frame": 29, "top_frame": 89, "impact_frame": 109}}
    metrics_path.write_text(json.dumps(original_metrics))
    metrics_before = metrics_path.read_bytes()

    result = analyze_session_what_if(
        directory,
        config,
        [{"camera": "camera_2", "frame_index": 120, "marker": "RHip"}],
    )

    assert result["diagnostic_only"] is True
    assert result["exclusions"] == [
        {
            "camera": "camera_2",
            "frame_index": 120,
            "marker": "RHip",
            "trc_frame_index": 60,
            "trc_time_s": pytest.approx(1.0),
        }
    ]
    assert result["metrics"]
    assert metrics_path.read_bytes() == metrics_before
    assert trc.read_bytes() == trc_before
    assert metadata_path.read_bytes() == metadata_before


def test_explicit_reconstruction_archives_existing_geometry_and_records_selection(measured_session):
    from golf_sim.pose.reconstruction_evidence import prepare_explicit_reconstruction

    directory, config, trc, snapshot = measured_session
    original = trc.read_bytes()
    prepare_explicit_reconstruction(directory, config, snapshot["bundle_id"])
    metadata = json.loads((directory / "metadata.json").read_text())
    archive = directory / metadata["reconstruction_history"][-1]["archive"]
    assert (archive / "pose-3d" / trc.name).read_bytes() == original
    assert not trc.exists()
    assert metadata["selected_calibration_bundle_id"] == snapshot["bundle_id"]


def test_incompatible_history_is_not_rewritten_by_explicit_request(measured_session):
    from golf_sim.pose.reconstruction_evidence import prepare_explicit_reconstruction

    directory, config, trc, snapshot = measured_session
    metadata = json.loads((directory / "metadata.json").read_text())
    metadata["cameras"]["camera_1"]["requested_fps"] = (
        60 if config.cameras.devices[0].fps != 60 else 120
    )
    atomic_json(directory / "metadata.json", metadata)
    with pytest.raises(ValueError, match="compatibility"):
        prepare_explicit_reconstruction(directory, config, snapshot["bundle_id"])
    assert trc.exists()
    assert not (directory / "reconstruction-history").exists()
