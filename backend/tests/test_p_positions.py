import numpy as np
import pytest

from golf_sim.analysis.p_positions import (
    arm_elevation_series,
    detect_p_positions,
    lead_markers,
)
from golf_sim.analysis.phases import detect_phases


def test_lead_markers_by_handedness():
    assert lead_markers("right") == ("LShoulder", "LWrist")
    assert lead_markers("left") == ("RShoulder", "RWrist")


def test_detects_ten_positions_in_monotonic_order(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    positions = detect_p_positions(synthetic_swing_full, phases, handedness="right")

    assert [p.name for p in positions] == [f"P{i}" for i in range(1, 11)]
    frames = [p.frame_index for p in positions]
    assert frames == sorted(frames)
    assert all(t >= 0 for t in (p.time_s for p in positions))


def test_p1_p4_p7_match_address_top_impact(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    positions = detect_p_positions(synthetic_swing_full, phases, handedness="right")
    by_name = {p.name: p for p in positions}

    assert by_name["P1"].frame_index == phases.address_frame
    assert by_name["P4"].frame_index == phases.top_frame
    assert by_name["P7"].frame_index == phases.impact_frame
    assert by_name["P1"].label == "Address"
    assert by_name["P4"].label == "Top of Backswing"
    assert by_name["P7"].label == "Impact"
    assert by_name["P10"].label == "Finish"


def test_backswing_checkpoints_between_address_and_top(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    positions = detect_p_positions(synthetic_swing_full, phases, handedness="right")
    by_name = {p.name: p.frame_index for p in positions}

    assert phases.address_frame <= by_name["P2"] <= by_name["P3"] <= phases.top_frame


def test_downswing_and_followthrough_checkpoints_bracket_impact(synthetic_swing_full):
    phases = detect_phases(synthetic_swing_full)
    positions = detect_p_positions(synthetic_swing_full, phases, handedness="right")
    by_name = {p.name: p.frame_index for p in positions}

    assert phases.top_frame <= by_name["P5"] <= by_name["P6"] <= phases.impact_frame
    assert phases.impact_frame <= by_name["P8"] <= by_name["P9"] <= by_name["P10"]


def test_arm_elevation_series_matches_known_geometry(synthetic_swing_full):
    # at address (rot_progress=0), hands are level with... check known synthetic
    # geometry: shoulder at (0,0.2,1.4), hand at (0.3,0,0.8) at address (progress=0)
    elevation = arm_elevation_series(synthetic_swing_full, "LShoulder", "LWrist")
    # address frame: hand is below shoulder -> negative elevation
    assert elevation[0] < 0
    # top of backswing: hand height 1.7 > shoulder height 1.4 -> positive elevation
    top_frame_idx = 30 + 60 - 1  # near end of backswing window
    assert elevation[top_frame_idx] > 0


def test_raises_reasonable_error_on_degenerate_input():
    from golf_sim.trc import LandmarkSequence

    names = ["Hip", "RHip", "LHip", "Neck", "Head", "RAnkle", "LAnkle", "RWrist", "LWrist"]
    coords = np.zeros((3, len(names), 3))
    seq = LandmarkSequence(marker_names=names, times=np.arange(3) / 60.0, coords=coords)
    from golf_sim.analysis.phases import PhaseDetectionError

    with pytest.raises(PhaseDetectionError):
        detect_phases(seq)
