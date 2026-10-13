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
    assert by_name["P1"].available is True
    assert by_name["P4"].available is True
    assert by_name["P7"].available is True
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


def test_unobserved_proxy_crossing_is_not_marked_as_detected():
    from golf_sim.analysis.phases import SwingPhases
    from golf_sim.trc import LandmarkSequence

    names = ["Hip", "Head", "RAnkle", "LAnkle", "LShoulder", "LWrist", "RWrist"]
    times = np.arange(20) / 60.0
    coords = np.zeros((20, len(names), 3))
    indices = {name: index for index, name in enumerate(names)}
    coords[:, indices["Head"], 2] = 1.8
    coords[:, indices["Hip"], 2] = 1.0
    coords[:, indices["LShoulder"], 2] = 1.4
    coords[:, indices["LWrist"], 0] = 1.0
    coords[:, indices["LWrist"], 2] = 1.4 + np.tan(np.radians(10))
    coords[:, indices["RWrist"]] = coords[:, indices["LWrist"]]

    seq = LandmarkSequence(marker_names=names, times=times, coords=coords)
    phases = SwingPhases(address_frame=2, top_frame=10, impact_frame=14)
    positions = detect_p_positions(seq, phases)
    by_name = {position.name: position for position in positions}

    assert by_name["P3"].available is False
    assert (
        by_name["P3"].unavailable_reason
        == "proxy target was not crossed and phase progress was not measurable"
    )
    assert by_name["P1"].available is True
    assert by_name["P4"].available is True
    assert by_name["P7"].available is True


def test_unobserved_proxy_uses_selectable_mid_phase_estimate():
    from golf_sim.analysis.phases import SwingPhases
    from golf_sim.trc import LandmarkSequence

    names = ["Hip", "Head", "RAnkle", "LAnkle", "LShoulder", "LWrist", "RWrist"]
    times = np.arange(20) / 60.0
    coords = np.zeros((20, len(names), 3))
    indices = {name: index for index, name in enumerate(names)}
    coords[:, indices["Head"], 2] = 1.8
    coords[:, indices["Hip"], 2] = 1.0
    coords[:, indices["LShoulder"], 2] = 1.4
    angles = np.radians(np.linspace(10, 70, len(times)))
    coords[:, indices["LWrist"], 0] = np.cos(angles)
    coords[:, indices["LWrist"], 2] = 1.4 + np.sin(angles)
    coords[:, indices["RWrist"]] = coords[:, indices["LWrist"]]

    seq = LandmarkSequence(marker_names=names, times=times, coords=coords)
    phases = SwingPhases(address_frame=2, top_frame=16, impact_frame=18)
    positions = detect_p_positions(seq, phases)
    by_name = {position.name: position for position in positions}

    assert by_name["P3"].available is True
    assert by_name["P3"].detected is False
    assert by_name["P3"].estimate_reason == "proxy target not crossed; phase-progress estimate used"
    assert phases.address_frame + 3 < by_name["P3"].frame_index < phases.top_frame - 3
