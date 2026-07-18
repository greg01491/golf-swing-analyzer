import numpy as np
import pytest

from golf_sim.analysis.ideal_pose import (
    build_all_ideal_frames,
    build_ideal_frame,
    measure_proportions,
)
from golf_sim.analysis.p_positions import detect_p_positions
from golf_sim.analysis.phases import detect_phases
from golf_sim.config import MetricsConfig, ReferenceRange


def _metrics_config(**overrides):
    ranges = {
        "shoulder_turn_deg": ReferenceRange(min=80, max=100),
        "hip_turn_deg": ReferenceRange(min=40, max=55),
    }
    ranges.update(overrides)
    return MetricsConfig(reference_ranges=ranges)


def _raw_angle(vec, horizontal_axes=(0, 1)):
    return float(np.degrees(np.arctan2(vec[horizontal_axes[1]], vec[horizontal_axes[0]])))


def test_measure_proportions_matches_known_synthetic_geometry(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    proportions = measure_proportions(synthetic_swing_full, phases.address_frame, "right")

    assert np.linalg.norm(proportions.shoulder_line_address) == pytest.approx(0.4, abs=1e-6)
    assert np.linalg.norm(proportions.hip_line_address) == pytest.approx(0.3, abs=1e-6)
    # elbow is the shoulder-wrist midpoint in the fixture, so both segments
    # are exactly half the total arm reach
    assert proportions.lead_upper_arm_len == pytest.approx(proportions.lead_forearm_len, abs=1e-9)
    assert proportions.lead_upper_arm_len > 0.3


def test_ideal_frame_rotation_matches_target_angle_exactly(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    proportions = measure_proportions(synthetic_swing_full, phases.address_frame, "right")

    ideal = build_ideal_frame(
        synthetic_swing_full,
        frame_idx=phases.top_frame,
        shoulder_turn_deg=45.0,
        hip_turn_deg=20.0,
        arm_elevation_deg=0.0,
        handedness="right",
        proportions=proportions,
    )
    shoulder_line = ideal["RShoulder"] - ideal["LShoulder"]
    hip_line = ideal["RHip"] - ideal["LHip"]

    # address baseline for both lines points along the pure-u axis (arctan2 == 0
    # in this fixture's geometry), so the ideal's raw angle equals the target
    assert _raw_angle(shoulder_line) == pytest.approx(45.0, abs=0.5)
    assert _raw_angle(hip_line) == pytest.approx(20.0, abs=0.5)


def test_p1_ideal_arms_equal_actual_arms(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    proportions = measure_proportions(synthetic_swing_full, phases.address_frame, "right")

    ideal = build_ideal_frame(
        synthetic_swing_full,
        frame_idx=phases.address_frame,
        shoulder_turn_deg=0.0,
        hip_turn_deg=0.0,
        arm_elevation_deg=None,
        handedness="right",
        proportions=proportions,
    )
    actual_wrist = synthetic_swing_full.marker("LWrist")[phases.address_frame]
    assert np.allclose(ideal["LWrist"], actual_wrist)


def test_trail_wrist_pinned_to_lead_wrist_when_idealized(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    proportions = measure_proportions(synthetic_swing_full, phases.address_frame, "right")

    ideal = build_ideal_frame(
        synthetic_swing_full,
        frame_idx=phases.top_frame,
        shoulder_turn_deg=45.0,
        hip_turn_deg=20.0,
        arm_elevation_deg=0.0,
        handedness="right",
        proportions=proportions,
    )
    assert np.allclose(ideal["RWrist"], ideal["LWrist"])


def test_build_all_ideal_frames_p4_matches_reference_range_midpoint(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    positions = detect_p_positions(synthetic_swing_full, phases, handedness="right")
    frame_by_name = {p.name: p.frame_index for p in positions}
    config = _metrics_config()

    frames = build_all_ideal_frames(
        synthetic_swing_full, phases, frame_by_name, config, handedness="right"
    )

    p4 = frames["P4"]
    shoulder_line = p4["RShoulder"] - p4["LShoulder"]
    # P4 target fraction is 1.0 -> full reference-range midpoint (90 deg),
    # signed to match the fixture's own (positive) backswing rotation
    assert _raw_angle(shoulder_line) == pytest.approx(90.0, abs=0.5)


def test_build_all_ideal_frames_covers_every_detected_position(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    positions = detect_p_positions(synthetic_swing_full, phases, handedness="right")
    frame_by_name = {p.name: p.frame_index for p in positions}
    config = _metrics_config()

    frames = build_all_ideal_frames(
        synthetic_swing_full, phases, frame_by_name, config, handedness="right"
    )

    assert set(frames.keys()) == {p.name for p in positions}
    for name, marker_frame in frames.items():
        assert set(marker_frame.keys()) == set(synthetic_swing_full.marker_names)
