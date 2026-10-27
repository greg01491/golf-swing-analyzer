"""Metrics engine tests against a synthetic swing with known ground truth.

The synthetic golfer stands z-up: 30 quiet address frames, a 60-frame
backswing (shoulders rotate to SHOULDER_TURN deg, hips to HIP_TURN deg,
hands rise), a 20-frame downswing back to address orientation with hands
dropping below address height, then a short follow-through rise.
"""

import numpy as np
import pytest

from golf_sim.analysis.cli import apply_review_exclusions, session_review_issues
from golf_sim.analysis.frame_of_reference import AnalysisReference
from golf_sim.analysis.metrics import compute_metrics
from golf_sim.analysis.p_positions import detect_p_positions
from golf_sim.analysis.phases import SwingPhases, detect_phases
from golf_sim.analysis.tips import generate_tips
from golf_sim.config import MetricsConfig, ReferenceRange, load_config
from golf_sim.trc import LandmarkSequence

FPS = 60.0
ADDRESS_FRAMES = 30
BACKSWING_FRAMES = 60
DOWNSWING_FRAMES = 20
FOLLOW_FRAMES = 20
SHOULDER_TURN = 90.0
HIP_TURN = 45.0
SPINE_TILT = np.degrees(np.arctan2(0.2, 0.4))  # ~26.57 deg
EXPECTED_METRICS = {
    "shoulder_turn_deg",
    "hip_turn_deg",
    "x_factor_deg",
    "spine_tilt_deg",
    "tempo_ratio",
    "hip_sway_top_pct",
    "hip_sway_impact_pct",
    "hip_rotation_impact_deg",
    "backswing_time_s",
    "downswing_time_s",
    "shoulder_tilt_impact_deg",
    "spine_angle_change_deg",
    "head_movement_cm",
    "early_extension_cm",
    "reverse_spine_deg",
    "knee_flex_deg",
    "lead_arm_deg",
    "hand_speed_impact_ms",
    "swing_plane_deg",
}


def _rot(width: float, angle_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Left/right marker offsets for a body line rotated by angle in x-y."""
    a = np.radians(angle_deg)
    half = np.array([np.cos(a), np.sin(a), 0.0]) * width / 2
    return -half, half


def synthetic_swing(shoulder_turn=SHOULDER_TURN, hip_turn=HIP_TURN) -> LandmarkSequence:
    n = ADDRESS_FRAMES + BACKSWING_FRAMES + DOWNSWING_FRAMES + FOLLOW_FRAMES
    times = np.arange(n) / FPS

    # swing progress p(t): 0 at address, 1 at top, back to 0 at impact
    progress = np.zeros(n)
    top_end = ADDRESS_FRAMES + BACKSWING_FRAMES
    impact_end = top_end + DOWNSWING_FRAMES
    progress[ADDRESS_FRAMES:top_end] = np.linspace(0, 1, BACKSWING_FRAMES)
    progress[top_end:impact_end] = np.linspace(1, 0, DOWNSWING_FRAMES)

    hand_height = np.full(n, 0.8)
    hand_height[ADDRESS_FRAMES:top_end] = 0.8 + 0.9 * progress[ADDRESS_FRAMES:top_end]
    hand_height[top_end:impact_end] = np.linspace(1.7, 0.7, DOWNSWING_FRAMES)
    hand_height[impact_end:] = np.linspace(0.7, 1.5, FOLLOW_FRAMES)

    marker_names = [
        "Hip",
        "RHip",
        "LHip",
        "Neck",
        "Head",
        "RAnkle",
        "LAnkle",
        "RShoulder",
        "LShoulder",
        "RElbow",
        "LElbow",
        "RWrist",
        "LWrist",
        "RKnee",
        "LKnee",
    ]
    coords = np.zeros((n, len(marker_names), 3))
    idx = {name: i for i, name in enumerate(marker_names)}

    for f in range(n):
        hip_center = np.array([0.0, 0.0, 1.0])
        shoulder_center = np.array([0.0, 0.2, 1.4])  # forward lean -> spine tilt
        coords[f, idx["Hip"]] = hip_center
        l_hip, r_hip = _rot(0.3, hip_turn * progress[f])
        coords[f, idx["LHip"]] = hip_center + l_hip
        coords[f, idx["RHip"]] = hip_center + r_hip
        l_sh, r_sh = _rot(0.4, shoulder_turn * progress[f])
        coords[f, idx["LShoulder"]] = shoulder_center + l_sh
        coords[f, idx["RShoulder"]] = shoulder_center + r_sh
        coords[f, idx["Neck"]] = shoulder_center
        coords[f, idx["Head"]] = shoulder_center + np.array([0.0, 0.0, 0.2])
        coords[f, idx["RAnkle"]] = np.array([0.2, 0.0, 0.05])
        coords[f, idx["LAnkle"]] = np.array([-0.2, 0.0, 0.05])
        hands = np.array([0.3, 0.3 * progress[f], hand_height[f]])
        coords[f, idx["RWrist"]] = hands
        coords[f, idx["LWrist"]] = hands
        coords[f, idx["RElbow"]] = (coords[f, idx["RShoulder"]] + hands) / 2
        coords[f, idx["LElbow"]] = (coords[f, idx["LShoulder"]] + hands) / 2
        coords[f, idx["RKnee"]] = np.array([0.2, 0.0, 0.55])
        coords[f, idx["LKnee"]] = np.array([-0.2, 0.0, 0.55])

    return LandmarkSequence(marker_names=marker_names, times=times, coords=coords)


def _config(**overrides) -> MetricsConfig:
    ranges = {
        "shoulder_turn_deg": ReferenceRange(min=80, max=100),
        "hip_turn_deg": ReferenceRange(min=40, max=55),
        "spine_tilt_deg": ReferenceRange(min=25, max=40),
        "x_factor_deg": ReferenceRange(min=30, max=45),
        "tempo_ratio": ReferenceRange(min=2.8, max=3.2),
    }
    ranges.update(overrides)
    return MetricsConfig(reference_ranges=ranges, range_definition_version=2)


def _known_evidence(seq):
    return {
        "reference": AnalysisReference(
            up=np.array([0, 0, 1]),
            target=np.array([-1, 0, 0]),
            ball=np.array([0, 1, 0]),
            source="synthetic_ground_truth",
        ),
        "marker_support": {name: np.ones(seq.n_frames, dtype=bool) for name in seq.marker_names},
    }


def test_review_issues_use_only_the_metrics_required_frames():
    seq = synthetic_swing()
    evidence = _known_evidence(seq)
    evidence["marker_support"]["Head"][40:43] = False
    evidence["marker_support"]["Head"][120:] = False
    phases = SwingPhases(address_frame=29, top_frame=89, impact_frame=109)

    payload = compute_metrics(seq, _config(), phases=phases, **evidence).to_dict()
    metrics = {metric["name"]: metric for metric in payload["metrics"]}

    assert metrics["head_movement_cm"]["review_issues"] == [
        {
            "marker": "Head",
            "reason": "Observation or reconstruction support rejected",
            "start_frame": 40,
            "end_frame": 42,
            "start_time_s": 40 / FPS,
            "end_time_s": 42 / FPS,
        }
    ]
    assert metrics["hip_turn_deg"]["review_issues"] == []
    assert metrics["lead_arm_deg"]["review_issues"] == []


def test_review_issues_do_not_invent_links_for_invalid_timestamps():
    import json

    seq = synthetic_swing()
    seq.times[40] = seq.times[39]
    evidence = _known_evidence(seq)
    evidence["marker_support"]["Head"][:] = False

    payload = compute_metrics(seq, _config(), phases=SwingPhases(29, 89, 109), **evidence).to_dict()

    assert all(not metric["review_issues"] for metric in payload["metrics"])
    assert all(
        any(reason.startswith("invalid_timestamps:") for reason in metric["reasons"])
        for metric in payload["metrics"]
    )
    json.dumps(payload, allow_nan=False)


def test_review_issue_diagnostic_maps_each_camera_without_writing(tmp_path, monkeypatch):
    import json

    import golf_sim.analysis.cli as analysis

    seq = synthetic_swing()
    seq.times += 1
    evidence = _known_evidence(seq)
    evidence["marker_support"]["Head"][:] = False
    trc_path = tmp_path / "saved.trc"
    trc_path.write_text("unchanged 3D")
    (tmp_path / "metrics.json").write_text(
        json.dumps(
            {
                "source_trc": trc_path.name,
                "phases": {"address_frame": 29, "top_frame": 89, "impact_frame": 109},
            }
        )
    )
    (tmp_path / "metadata.json").write_text(
        json.dumps({"cameras": {"camera_1": {"fps": 120}, "camera_2": {"fps": 60}}})
    )
    (tmp_path / "review_annotations.json").write_text('{"version": 1}')
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    monkeypatch.setattr(analysis, "pick_trc", lambda directory: trc_path)
    monkeypatch.setattr(analysis, "read_trc", lambda path: seq)
    monkeypatch.setattr(analysis, "_reference_for_session", lambda *args: evidence["reference"])
    monkeypatch.setattr(
        analysis, "_marker_observation_support", lambda *args: evidence["marker_support"]
    )
    monkeypatch.setattr(analysis, "verified_artifact_evidence", lambda path: None)

    result = session_review_issues(tmp_path, load_config())

    head_rows = [row for row in result["issues"] if row["marker"] == "Head"]
    assert {row["camera"] for row in head_rows} == {"camera_1", "camera_2"}
    first = {row["camera"]: row["frame_indices"][0] for row in head_rows}
    assert first == {"camera_1": 178, "camera_2": 89}
    assert all(row["camera_attribution"] == "not_isolated" for row in head_rows)
    assert all(row["metric"] == "head_movement_cm" for row in head_rows)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before

    failure = {
        "reason": "Reprojection error exceeds tolerance",
        "value": 28,
        "threshold": 15,
        "unit": "px",
    }
    monkeypatch.setattr(
        analysis,
        "review_camera_tolerances",
        lambda *args: {
            "available": True,
            "reason": None,
            "failures": {"camera_1/Head/178": failure},
        },
    )
    filtered = session_review_issues(tmp_path, load_config())
    assert len(filtered["tolerance_issues"]) == 1
    assert filtered["tolerance_issues"][0]["camera"] == "camera_1"
    assert filtered["tolerance_issues"][0]["frame_indices"] == [178]
    assert filtered["tolerance_issues"][0]["measurements"] == {"178": failure}
    assert len(filtered["issues"]) == len(result["issues"])
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before

    (tmp_path / "metadata.json").write_text(json.dumps({"cameras": {"camera_1": {}}}))
    unmapped = session_review_issues(tmp_path, load_config())
    assert all(not row["frame_indices"] for row in unmapped["issues"])
    assert all(row["mapping_reason"] for row in unmapped["issues"])
    assert unmapped["tolerance_issues"] == []


def test_phase_detection_finds_address_top_impact():
    seq = synthetic_swing()
    phases = detect_phases(seq)

    assert phases.address_frame == pytest.approx(ADDRESS_FRAMES, abs=3)
    assert phases.top_frame == pytest.approx(ADDRESS_FRAMES + BACKSWING_FRAMES, abs=3)
    assert phases.impact_frame == pytest.approx(
        ADDRESS_FRAMES + BACKSWING_FRAMES + DOWNSWING_FRAMES, abs=3
    )


def test_metrics_match_synthetic_ground_truth():
    seq = synthetic_swing()
    report = compute_metrics(seq, _config(), **_known_evidence(seq))
    by_name = {m.name: m for m in report.metrics}

    assert by_name["shoulder_turn_deg"].value == pytest.approx(SHOULDER_TURN, abs=2)
    assert by_name["hip_turn_deg"].value == pytest.approx(HIP_TURN, abs=2)
    assert by_name["x_factor_deg"].value == pytest.approx(SHOULDER_TURN - HIP_TURN, abs=2)
    assert by_name["spine_tilt_deg"].value == pytest.approx(SPINE_TILT, abs=1)
    assert by_name["tempo_ratio"].value == pytest.approx(
        BACKSWING_FRAMES / DOWNSWING_FRAMES, abs=0.4
    )
    assert by_name["hip_sway_top_pct"].value == pytest.approx(0, abs=2)


def test_in_range_flags():
    seq = synthetic_swing()
    report = compute_metrics(seq, _config(), **_known_evidence(seq))
    by_name = {m.name: m for m in report.metrics}

    assert by_name["shoulder_turn_deg"].in_range is True
    assert by_name["tempo_ratio"].in_range is True
    # no range configured for sway in this config -> unflagged
    assert by_name["hip_sway_top_pct"].in_range is None


def test_restricted_turn_is_flagged_out_of_range():
    seq = synthetic_swing(shoulder_turn=60.0)
    report = compute_metrics(seq, _config(), **_known_evidence(seq))
    by_name = {m.name: m for m in report.metrics}

    assert by_name["shoulder_turn_deg"].value == pytest.approx(60, abs=2)
    assert by_name["shoulder_turn_deg"].in_range is False


def test_club_profile_overrides_only_club_specific_ranges():
    config = _config()
    config.club_profiles["wedge"] = {
        "spine_tilt_deg": ReferenceRange(min=35, max=50),
    }
    config.club_profile_mapping["pitching_wedge"] = "wedge"

    seq = synthetic_swing()
    report = compute_metrics(seq, config, club="pitching_wedge", **_known_evidence(seq))
    by_name = {m.name: m for m in report.metrics}

    assert by_name["spine_tilt_deg"].range_min == 35
    assert by_name["spine_tilt_deg"].in_range is False
    assert by_name["tempo_ratio"].range_min == 2.8


def test_report_serializes_to_dict():
    seq = synthetic_swing()
    report = compute_metrics(seq, _config())
    payload = report.to_dict()

    assert set(payload) == {"phases", "metrics", "analysis_version", "reference_frame"}
    assert all({"name", "value", "unit", "in_range", "range"} <= set(m) for m in payload["metrics"])


def test_extended_metrics_present_and_sane():
    seq = synthetic_swing()
    report = compute_metrics(seq, _config(), **_known_evidence(seq))
    by_name = {m.name: m for m in report.metrics}

    # The synthetic golfer's head and hips are fixed and the body returns to
    # address orientation at impact, so the "stability" faults read ~0.
    assert by_name["head_movement_cm"].value == pytest.approx(0, abs=1)
    assert by_name["spine_angle_change_deg"].value == pytest.approx(0, abs=1)
    assert by_name["early_extension_cm"].value == pytest.approx(0, abs=1)
    assert by_name["reverse_spine_deg"].value == pytest.approx(0, abs=1)
    assert by_name["hip_rotation_impact_deg"].value == pytest.approx(0, abs=3)

    # Raw halves of the tempo ratio.
    assert by_name["backswing_time_s"].value == pytest.approx(BACKSWING_FRAMES / FPS, abs=0.1)
    assert by_name["downswing_time_s"].value == pytest.approx(DOWNSWING_FRAMES / FPS, abs=0.1)

    # Speed and plane are finite and positive for a real motion.
    assert by_name["hand_speed_impact_ms"].value > 0
    assert np.isfinite(by_name["swing_plane_deg"].value)


def test_shipped_config_ranges_every_finite_metric():
    seq = synthetic_swing()
    report = compute_metrics(seq, load_config().metrics, club="driver", **_known_evidence(seq))

    assert {metric.name for metric in report.metrics} == EXPECTED_METRICS
    for metric in report.metrics:
        if np.isfinite(metric.value):
            assert metric.range_min is not None, metric.name
            assert metric.range_max is not None, metric.name
            assert metric.in_range is not None, metric.name


@pytest.mark.parametrize("artifact", ["spike", "swap"])
def test_isolated_shoulder_artifact_cannot_become_peak(artifact):
    seq = synthetic_swing()
    frame = 55
    left = seq.marker_names.index("LShoulder")
    right = seq.marker_names.index("RShoulder")
    if artifact == "swap":
        seq.coords[frame, [left, right]] = seq.coords[frame, [right, left]]
    else:
        center = (seq.coords[frame, left] + seq.coords[frame, right]) / 2
        offset = np.array([np.cos(np.radians(160)), np.sin(np.radians(160)), 0]) * 0.2
        seq.coords[frame, left] = center - offset
        seq.coords[frame, right] = center + offset

    metrics = {metric.name: metric for metric in compute_metrics(seq, _config()).metrics}

    assert metrics["shoulder_turn_deg"].value == pytest.approx(90, abs=3)
    assert metrics["x_factor_deg"].value == pytest.approx(45, abs=3)


def test_head_excursion_is_not_hidden_by_return_to_address():
    seq = synthetic_swing()
    seq.coords[60, seq.marker_names.index("Head"), 0] += 0.3

    metrics = {metric.name: metric for metric in compute_metrics(seq, _config()).metrics}

    assert metrics["head_movement_cm"].value == pytest.approx(30, abs=0.01)


def test_x_factor_cannot_exceed_circular_separation():
    seq = synthetic_swing(shoulder_turn=179, hip_turn=-179)

    metrics = {metric.name: metric for metric in compute_metrics(seq, _config()).metrics}

    assert 0 <= metrics["x_factor_deg"].value <= 180


def test_collapsed_shoulder_line_is_not_zero_rotation():
    seq = synthetic_swing()
    seq.coords[:, seq.marker_names.index("RShoulder")] = seq.marker("LShoulder")

    metrics = {metric.name: metric for metric in compute_metrics(seq, _config()).metrics}

    assert metrics["shoulder_turn_deg"].status == "unavailable"
    assert metrics["shoulder_turn_deg"].in_range is None


def test_frozen_torso_is_not_validated_by_moving_wrists():
    seq = synthetic_swing()
    for marker in ("LShoulder", "RShoulder", "LHip", "RHip"):
        index = seq.marker_names.index(marker)
        seq.coords[:, index] = seq.coords[0, index]

    metrics = {metric.name: metric for metric in compute_metrics(seq, _config()).metrics}

    assert metrics["shoulder_turn_deg"].status != "valid"
    assert metrics["hip_turn_deg"].status != "valid"


def test_reference_normalizes_vectors_and_rejects_invalid_geometry():
    reference = AnalysisReference(up=np.array([0, 0, 2]), target=np.array([-2, 0, 1]))

    assert reference.up == pytest.approx([0, 0, 1])
    assert reference.target == pytest.approx([-1, 0, 0])
    with pytest.raises(ValueError, match="nonzero"):
        AnalysisReference(up=np.zeros(3))
    with pytest.raises(ValueError, match="perpendicular"):
        AnalysisReference(
            up=np.array([0, 0, 1]), target=np.array([1, 0, 0]), ball=np.array([1, 0, 0])
        )


def test_all_definitions_against_known_geometry_and_times():
    seq = synthetic_swing()
    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )
    expected = {
        "shoulder_turn_deg": (90, 1.6),
        "hip_turn_deg": (45, 0.8),
        "x_factor_deg": (45, 0.8),
        "spine_tilt_deg": (26.565051, 0.001),
        "tempo_ratio": (3, 0.001),
        "hip_sway_top_pct": (0, 0.001),
        "hip_sway_impact_pct": (0, 0.001),
        "hip_rotation_impact_deg": (0, 1.2),
        "backswing_time_s": (1, 0.001),
        "downswing_time_s": (1 / 3, 0.001),
        "shoulder_tilt_impact_deg": (0, 0.001),
        "spine_angle_change_deg": (0, 0.001),
        "head_movement_cm": (0, 0.001),
        "early_extension_cm": (0, 0.001),
        "reverse_spine_deg": (0, 0.001),
        "knee_flex_deg": (173.659808, 0.001),
        "lead_arm_deg": (180, 0.001),
        "hand_speed_impact_ms": (3.296693, 0.001),
        "swing_plane_deg": (71.565051, 0.001),
    }
    assert set(expected) == EXPECTED_METRICS
    for metric in report.metrics:
        value, tolerance = expected[metric.name]
        assert metric.value == pytest.approx(value, abs=tolerance), metric.name
        assert metric.status == "valid", metric.name


def test_unverified_reference_cannot_receive_target_verdicts():
    report = compute_metrics(synthetic_swing(), _config())
    metrics = {metric.name: metric for metric in report.metrics}

    assert metrics["shoulder_turn_deg"].status == "estimated"
    assert metrics["shoulder_turn_deg"].in_range is None
    assert metrics["early_extension_cm"].status == "unavailable"


@pytest.mark.parametrize("angle", [30, 90, 170])
def test_metric_geometry_is_invariant_under_rigid_coordinate_transform(angle):
    seq = synthetic_swing()
    evidence = _known_evidence(seq)
    original = compute_metrics(seq, _config(), phases=SwingPhases(29, 89, 109), **evidence)
    radians = np.radians(angle)
    rotation = np.array(
        [
            [np.cos(radians), 0, np.sin(radians)],
            [0, 1, 0],
            [-np.sin(radians), 0, np.cos(radians)],
        ]
    )
    seq.coords = seq.coords @ rotation.T + np.array([3, -7, 2])
    reference = evidence["reference"]
    evidence["reference"] = AnalysisReference(
        up=rotation @ reference.up,
        target=rotation @ reference.target,
        ball=rotation @ reference.ball,
        source="synthetic_ground_truth",
    )

    transformed = compute_metrics(seq, _config(), phases=SwingPhases(29, 89, 109), **evidence)

    for before, after in zip(original.metrics, transformed.metrics, strict=True):
        assert after.value == pytest.approx(before.value, abs=0.0001), before.name
        assert after.status == before.status == "valid", before.name


@pytest.mark.parametrize("handedness", ["right", "left"])
@pytest.mark.parametrize("direction", [-1, 1])
def test_posture_direction_is_preserved(handedness, direction):
    seq = synthetic_swing()
    phases = SwingPhases(29, 89, 109)
    evidence = _known_evidence(seq)
    if handedness == "left":
        evidence["reference"].target *= -1
    target = evidence["reference"].target
    seq.coords[phases.top_frame, seq.marker_names.index("Neck")] += target * direction * 0.1
    seq.coords[phases.impact_frame, seq.marker_names.index("Hip"), 1] += direction * 0.1
    report = compute_metrics(seq, _config(), phases=phases, handedness=handedness, **evidence)
    metrics = {metric.name: metric for metric in report.metrics}

    assert metrics["reverse_spine_deg"].value == pytest.approx(direction * 14.036243, abs=0.001)
    assert metrics["early_extension_cm"].value == pytest.approx(direction * 10, abs=0.001)
    assert metrics["spine_tilt_deg"].value == pytest.approx(26.565051, abs=0.001)


def test_missing_shoulder_does_not_remove_independent_knee_measurement():
    seq = synthetic_swing()
    index = seq.marker_names.index("LShoulder")
    seq.coords = np.delete(seq.coords, index, axis=1)
    seq.marker_names.pop(index)

    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )
    metrics = {metric.name: metric for metric in report.metrics}

    assert set(metrics) == EXPECTED_METRICS
    assert metrics["shoulder_turn_deg"].status == "unavailable"
    assert metrics["x_factor_deg"].status == "unavailable"
    assert metrics["knee_flex_deg"].status == "valid"


def test_supported_still_head_is_not_assumed_gap_filled():
    seq = synthetic_swing()
    report = compute_metrics(seq, _config(), **_known_evidence(seq))
    metric = next(metric for metric in report.metrics if metric.name == "head_movement_cm")

    assert metric.status == "valid"
    assert metric.value == 0


def test_invalid_timestamps_cannot_produce_valid_metrics():
    seq = synthetic_swing()
    seq.times[60] = seq.times[59]

    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )

    assert all(metric.status == "unavailable" for metric in report.metrics)
    assert all(metric.in_range is None for metric in report.metrics)


def test_unavailable_values_are_strict_json_nulls():
    import json

    seq = synthetic_swing()
    seq.coords[:, seq.marker_names.index("RShoulder")] = seq.marker("LShoulder")
    report = compute_metrics(seq, _config())

    serialized = json.dumps(report.to_dict(), allow_nan=False)
    payload = json.loads(serialized)
    metric = next(metric for metric in payload["metrics"] if metric["name"] == "shoulder_turn_deg")

    assert metric["value"] is None
    assert metric["status"] == "unavailable"
    assert metric["in_range"] is None


def test_implausible_reconstructed_scale_is_not_a_valid_measurement():
    seq = synthetic_swing()
    seq.coords *= 1000

    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )

    assert all(metric.status == "unavailable" for metric in report.metrics)


def test_unsupported_turn_sample_does_not_supply_the_peak():
    seq = synthetic_swing()
    evidence = _known_evidence(seq)
    evidence["marker_support"]["LShoulder"][80:95] = False
    report = compute_metrics(seq, _config(), phases=SwingPhases(29, 89, 109), **evidence)
    metric = next(metric for metric in report.metrics if metric.name == "shoulder_turn_deg")

    assert metric.value < 80


def test_p_positions_remain_available_when_unrelated_metric_evidence_fails():
    seq = synthetic_swing()
    phases = SwingPhases(29, 89, 109)
    positions = detect_p_positions(seq, phases)
    evidence = _known_evidence(seq)
    evidence["marker_support"]["LShoulder"][phases.address_frame : phases.top_frame + 1] = False

    report = compute_metrics(seq, _config(), phases=phases, **evidence)
    metrics = {metric.name: metric for metric in report.metrics}

    assert len(positions) == 10
    assert all(position.available for position in positions)
    assert metrics["shoulder_turn_deg"].status == "unavailable"
    assert any("insufficient_coverage" in reason for reason in metrics["shoulder_turn_deg"].reasons)
    assert np.isfinite(metrics["backswing_time_s"].value)
    assert metrics["backswing_time_s"].status == "valid"


@pytest.mark.parametrize("range_version", [None, 1, 99])
def test_incompatible_range_version_preserves_estimate_without_verdict(range_version):
    seq = synthetic_swing()
    config = _config()
    config.range_definition_version = range_version
    report = compute_metrics(seq, config, **_known_evidence(seq))
    metric = next(metric for metric in report.metrics if metric.name == "shoulder_turn_deg")

    assert np.isfinite(metric.value)
    assert metric.status == "estimated"
    assert metric.range_min is None
    assert metric.in_range is None
    assert any("incompatible_target" in reason for reason in metric.reasons)
    assert all(tip.metric != "shoulder_turn_deg" for tip in generate_tips(report))
    serialized = next(
        item for item in report.to_dict()["metrics"] if item["name"] == "shoulder_turn_deg"
    )
    assert serialized["value"] == pytest.approx(metric.value, abs=0.01)
    assert serialized["status"] == "estimated"
    assert serialized["in_range"] is None


def test_review_exclusion_maps_camera_frame_and_masks_only_a_copy():
    seq = synthetic_swing()
    support = {name: np.ones(seq.n_frames, dtype=bool) for name in seq.marker_names}
    original_head = seq.marker("Head").copy()

    diagnostic, diagnostic_support, applied = apply_review_exclusions(
        seq,
        support,
        {"camera_1": 60.0, "camera_2": 120.0},
        [{"camera": "camera_2", "frame_index": 120, "marker": "RHip"}],
    )

    assert applied == [
        {
            "camera": "camera_2",
            "frame_index": 120,
            "marker": "RHip",
            "trc_frame_index": 60,
            "trc_time_s": pytest.approx(1.0),
        }
    ]
    assert np.isnan(diagnostic.marker("RHip")[60]).all()
    assert diagnostic_support["RHip"][60] is np.False_
    assert np.isfinite(seq.marker("RHip")[60]).all()
    assert support["RHip"].all()
    assert np.array_equal(seq.marker("Head"), original_head)


@pytest.mark.parametrize(
    "field,value",
    [("turn_filter_window_s", 0), ("min_supported_fraction", 2), ("max_pelvis_height_m", 0.1)],
)
def test_evidence_settings_reject_invalid_values(field, value):
    with pytest.raises(ValueError):
        MetricsConfig(reference_ranges={}, **{field: value})


def test_legacy_configuration_loads_conservative_evidence_defaults():
    config = MetricsConfig(reference_ranges={})
    assert config.range_definition_version is None
    assert config.turn_filter_window_s == 0.05
    assert config.hand_speed_window_s == 0.1


def test_mirrored_handedness_preserves_anatomical_measurements():
    seq = synthetic_swing()
    evidence = _known_evidence(seq)
    phases = SwingPhases(29, 89, 109)
    before = compute_metrics(seq, _config(), phases=phases, **evidence)
    mirror = np.diag([-1, 1, 1])
    seq.coords = seq.coords @ mirror
    reference = evidence["reference"]
    evidence["reference"] = AnalysisReference(
        up=mirror @ reference.up,
        target=mirror @ reference.target,
        ball=mirror @ reference.ball,
    )
    after = compute_metrics(seq, _config(), phases=phases, handedness="left", **evidence)
    for first, second in zip(before.metrics, after.metrics, strict=True):
        assert second.value == pytest.approx(first.value, abs=0.0001), first.name
        assert second.status == first.status


@pytest.mark.parametrize("fps", [30, 120])
def test_turn_filter_uses_time_not_fixed_frame_count(fps):
    seq = synthetic_swing()
    times = np.arange(0, seq.times[-1], 1 / fps)
    flattened = seq.coords.reshape(seq.n_frames, -1)
    coords = np.column_stack([np.interp(times, seq.times, column) for column in flattened.T])
    seq.coords = coords.reshape(len(times), len(seq.marker_names), 3)
    seq.times = times
    phases = SwingPhases(round(29 / 60 * fps), round(89 / 60 * fps), round(109 / 60 * fps))
    report = compute_metrics(seq, _config(), phases=phases, **_known_evidence(seq))
    metrics = {metric.name: metric for metric in report.metrics}
    assert metrics["shoulder_turn_deg"].value == pytest.approx(90, abs=3)
    assert metrics["hip_turn_deg"].value == pytest.approx(45, abs=1.5)


def test_contaminated_address_sample_does_not_rotate_the_baseline():
    seq = synthetic_swing()
    frame = 29
    center = (seq.marker("LShoulder")[frame] + seq.marker("RShoulder")[frame]) / 2
    left, right = _rot(0.4, 170)
    seq.coords[frame, seq.marker_names.index("LShoulder")] = center + left
    seq.coords[frame, seq.marker_names.index("RShoulder")] = center + right
    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )
    metric = next(metric for metric in report.metrics if metric.name == "shoulder_turn_deg")
    assert metric.value == pytest.approx(90, abs=2)


@pytest.mark.parametrize("direction", [-1, 1])
@pytest.mark.parametrize("handedness", ["right", "left"])
def test_impact_rotation_and_shoulder_tilt_have_anatomical_signs(direction, handedness):
    seq = synthetic_swing()
    evidence = _known_evidence(seq)
    phases = SwingPhases(29, 89, 109)
    side = 1 if handedness == "right" else -1
    evidence["reference"].target *= side
    left, right = _rot(0.3, direction * side * 35)
    for frame in range(105, 114):
        seq.coords[frame, seq.marker_names.index("LHip")] = seq.marker("Hip")[frame] + left
        seq.coords[frame, seq.marker_names.index("RHip")] = seq.marker("Hip")[frame] + right
    lead = "LShoulder" if handedness == "right" else "RShoulder"
    trail = "RShoulder" if handedness == "right" else "LShoulder"
    seq.coords[109, seq.marker_names.index(lead), 2] += direction * 0.1
    seq.coords[109, seq.marker_names.index(trail), 2] -= direction * 0.1
    report = compute_metrics(seq, _config(), phases=phases, handedness=handedness, **evidence)
    metrics = {metric.name: metric for metric in report.metrics}
    assert metrics["hip_rotation_impact_deg"].value == pytest.approx(direction * 35, abs=0.001)
    assert metrics["shoulder_tilt_impact_deg"].value == pytest.approx(
        direction * 26.565051, abs=0.001
    )


def test_lateral_bend_does_not_become_forward_posture_change():
    seq = synthetic_swing()
    seq.coords[109, seq.marker_names.index("Neck"), 0] += 0.2
    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )
    metric = next(metric for metric in report.metrics if metric.name == "spine_angle_change_deg")
    assert metric.value == pytest.approx(0, abs=0.001)


def test_degenerate_joint_stance_and_hand_path_are_unavailable():
    seq = synthetic_swing()
    seq.coords[:, seq.marker_names.index("LAnkle")] = seq.marker("RAnkle")
    seq.coords[29, seq.marker_names.index("LKnee")] = seq.marker("LHip")[29]
    seq.coords[89, seq.marker_names.index("LWrist")] = seq.marker("LWrist")[29]
    seq.coords[89, seq.marker_names.index("RWrist")] = seq.marker("RWrist")[29]
    seq.coords[89, seq.marker_names.index("LElbow")] = seq.marker("LWrist")[89]
    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )
    metrics = {metric.name: metric for metric in report.metrics}
    for name in (
        "hip_sway_top_pct",
        "hip_sway_impact_pct",
        "knee_flex_deg",
        "lead_arm_deg",
        "swing_plane_deg",
    ):
        assert metrics[name].status == "unavailable", name


@pytest.mark.parametrize("irregular", [False, True])
def test_wrist_speed_uses_actual_time_intervals_and_rejects_isolated_jump(irregular):
    seq = synthetic_swing()
    if irregular:
        seq.times = np.cumsum(np.resize([0.01, 0.02], seq.n_frames))
    for name in ("LWrist", "RWrist"):
        seq.coords[:, seq.marker_names.index(name)] = np.column_stack(
            (seq.times * 4, np.zeros(seq.n_frames), np.full(seq.n_frames, 0.8))
        )
    seq.coords[107, seq.marker_names.index("LWrist"), 1] += 0.1
    report = compute_metrics(
        seq, _config(), phases=SwingPhases(29, 89, 109), **_known_evidence(seq)
    )
    metric = next(metric for metric in report.metrics if metric.name == "hand_speed_impact_ms")
    assert metric.value == pytest.approx(4, abs=0.001)


def test_estimated_phases_and_reference_propagate_without_discarding_joint_geometry():
    seq = synthetic_swing()
    evidence = _known_evidence(seq)
    evidence["reference"].status = "estimated"
    phases = SwingPhases(29, 89, 109, status="estimated")
    report = compute_metrics(seq, _config(), phases=phases, **evidence)
    assert all(metric.status == "estimated" for metric in report.metrics)
    assert all(metric.in_range is None for metric in report.metrics)


def test_inferred_reference_does_not_follow_corrupt_head():
    from golf_sim.analysis.frame_of_reference import infer_reference

    seq = synthetic_swing()
    before = infer_reference(seq)
    seq.coords[:, seq.marker_names.index("Head")] = np.array([100, -100, 0])
    after = infer_reference(seq)
    assert after.up == pytest.approx(before.up)
    assert after.status == "estimated"


def test_conflicting_body_axis_is_not_promoted_to_a_ground_reference():
    from golf_sim.analysis.frame_of_reference import infer_reference

    seq = synthetic_swing()
    seq.coords[:, seq.marker_names.index("Neck"), 2] = 0.5
    reference = infer_reference(seq)
    assert reference.status == "unavailable"
    report = compute_metrics(seq, _config(), phases=SwingPhases(29, 89, 109), reference=reference)
    metrics = {metric.name: metric for metric in report.metrics}
    assert metrics["shoulder_turn_deg"].status == "unavailable"
    assert metrics["knee_flex_deg"].status == "estimated"


def test_shared_reference_preserves_phase_checkpoint_and_overlay_geometry():
    from golf_sim.analysis.ideal_pose import build_all_ideal_frames
    from golf_sim.analysis.p_positions import detect_p_positions

    seq = synthetic_swing()
    reference = _known_evidence(seq)["reference"]
    before = detect_phases(seq, reference=reference)
    positions = detect_p_positions(seq, before, reference=reference)
    frames = {position.name: position.frame_index for position in positions}
    ideal = build_all_ideal_frames(seq, before, frames, _config(), reference=reference)
    radians = np.radians(30)
    rotation = np.array(
        [[1, 0, 0], [0, np.cos(radians), -np.sin(radians)], [0, np.sin(radians), np.cos(radians)]]
    )
    translation = np.array([2, -3, 4])
    seq.coords = seq.coords @ rotation.T + translation
    transformed_reference = AnalysisReference(
        rotation @ reference.up,
        rotation @ reference.target,
        rotation @ reference.ball,
    )
    after = detect_phases(seq, reference=transformed_reference)
    transformed_positions = detect_p_positions(seq, after, reference=transformed_reference)
    transformed_ideal = build_all_ideal_frames(
        seq, after, frames, _config(), reference=transformed_reference
    )

    assert after == before
    for first, second in zip(positions, transformed_positions, strict=True):
        assert second.frame_index == pytest.approx(first.frame_index, abs=1)
    for name, markers in ideal.items():
        for marker, point in markers.items():
            assert transformed_ideal[name][marker] == pytest.approx(
                rotation @ point + translation, abs=0.0001
            )
