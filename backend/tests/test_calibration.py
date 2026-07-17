import pytest

from golf_sim.audio.calibration import run_calibration, suggest_threshold_db
from golf_sim.audio.source import SyntheticAudioSource


def test_suggest_threshold_is_between_ambient_and_impact():
    threshold = suggest_threshold_db(
        ambient_levels=[-40.0, -38.0, -42.0], impact_levels=[-10.0, -8.0], margin_fraction=0.5
    )
    assert -38.0 < threshold < -8.0


def test_suggest_threshold_raises_when_impact_overlaps_ambient():
    with pytest.raises(ValueError):
        suggest_threshold_db(ambient_levels=[-10.0], impact_levels=[-15.0])


def test_run_calibration_end_to_end_with_synthetic_source():
    # quiet ambient, then three louder "impact" bursts
    amplitudes = [0.001] * 40 + [0.5] * 5 + [0.001] * 5 + [0.5] * 5 + [0.001] * 5 + [0.5] * 5
    source = SyntheticAudioSource(amplitudes=amplitudes, block_size=256)

    prompts: list[str] = []
    threshold = run_calibration(
        source,
        ambient_duration_s=0.2,
        num_impacts=3,
        impact_window_s=0.05,
        prompt=prompts.append,
        wait_for_user=lambda _msg: None,
    )

    assert threshold > -60.0  # clears the quiet ambient floor
    assert threshold < -6.0  # below the full impact peak
    assert any("Suggested threshold_db" in p for p in prompts)
