"""Metrics engine tests against a synthetic swing with known ground truth.

The synthetic golfer stands z-up: 30 quiet address frames, a 60-frame
backswing (shoulders rotate to SHOULDER_TURN deg, hips to HIP_TURN deg,
hands rise), a 20-frame downswing back to address orientation with hands
dropping below address height, then a short follow-through rise.
"""

import numpy as np
import pytest

from golf_sim.analysis.metrics import compute_metrics
from golf_sim.analysis.phases import detect_phases
from golf_sim.config import MetricsConfig, ReferenceRange
from golf_sim.trc import LandmarkSequence

FPS = 60.0
ADDRESS_FRAMES = 30
BACKSWING_FRAMES = 60
DOWNSWING_FRAMES = 20
FOLLOW_FRAMES = 20
SHOULDER_TURN = 90.0
HIP_TURN = 45.0
SPINE_TILT = np.degrees(np.arctan2(0.2, 0.4))  # ~26.57 deg


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
        "RWrist",
        "LWrist",
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
    return MetricsConfig(reference_ranges=ranges)


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
    report = compute_metrics(seq, _config())
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
    report = compute_metrics(seq, _config())
    by_name = {m.name: m for m in report.metrics}

    assert by_name["shoulder_turn_deg"].in_range is True
    assert by_name["tempo_ratio"].in_range is True
    # no range configured for sway in this config -> unflagged
    assert by_name["hip_sway_top_pct"].in_range is None


def test_restricted_turn_is_flagged_out_of_range():
    seq = synthetic_swing(shoulder_turn=60.0)
    report = compute_metrics(seq, _config())
    by_name = {m.name: m for m in report.metrics}

    assert by_name["shoulder_turn_deg"].value == pytest.approx(60, abs=2)
    assert by_name["shoulder_turn_deg"].in_range is False


def test_report_serializes_to_dict():
    seq = synthetic_swing()
    report = compute_metrics(seq, _config())
    payload = report.to_dict()

    assert set(payload) == {"phases", "metrics"}
    assert all({"name", "value", "unit", "in_range", "range"} <= set(m) for m in payload["metrics"])
