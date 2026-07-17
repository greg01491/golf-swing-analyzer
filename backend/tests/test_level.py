import numpy as np
import pytest

from golf_sim.audio.level import compute_level_db


def test_silence_is_very_low_db():
    assert compute_level_db(np.zeros(1000)) < -100


def test_full_scale_sine_is_near_zero_db():
    t = np.linspace(0, 4 * np.pi, 10000)
    level = compute_level_db(np.sin(t))
    assert level == pytest.approx(-3.01, abs=0.1)


def test_half_amplitude_constant_is_minus_6db():
    level = compute_level_db(np.full(1000, 0.5))
    assert level == pytest.approx(-6.02, abs=0.01)


def test_louder_block_has_higher_level():
    quiet = compute_level_db(np.full(1000, 0.01))
    loud = compute_level_db(np.full(1000, 0.5))
    assert loud > quiet
