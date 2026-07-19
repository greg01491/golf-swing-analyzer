import numpy as np

from golf_sim.analysis.quality import assess_tracking_quality
from golf_sim.trc import LandmarkSequence


def _seq(hands_per_frame: np.ndarray) -> LandmarkSequence:
    # minimal sequence with just the two wrist markers the assessor reads;
    # both wrists set equal so their midpoint is exactly hands_per_frame
    n = len(hands_per_frame)
    coords = np.zeros((n, 2, 3))
    coords[:, 0, :] = hands_per_frame
    coords[:, 1, :] = hands_per_frame
    return LandmarkSequence(
        times=np.arange(n) / 60.0, coords=coords, marker_names=["RWrist", "LWrist"]
    )


def test_clean_swing_is_reliable():
    # smooth, plausible-scale vertical arc (~1.4 m of travel)
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 0.7 * np.sin(t), np.zeros_like(t)], axis=1)
    q = assess_tracking_quality(_seq(hands))
    assert q.reliable is True
    assert q.warnings == []
    assert q.moving_fraction > 0.9


def test_frozen_gapfilled_sequence_flagged():
    # mostly held (gap-filled) values: one position repeated, a couple jumps
    hands = np.zeros((100, 3))
    hands[50:] = [0.0, 1.0, 0.0]  # a single jump; every other step is 0
    q = assess_tracking_quality(_seq(hands))
    assert q.reliable is False
    assert any("estimated" in w for w in q.warnings)


def test_implausible_scale_flagged():
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 5.0 * np.sin(t), np.zeros_like(t)], axis=1)  # 5 m travel
    q = assess_tracking_quality(_seq(hands))
    assert q.reliable is False
    assert any("physically impossible" in w for w in q.warnings)
