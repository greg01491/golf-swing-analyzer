"""Suggests a trigger threshold from a short ambient + impact recording
(tasks.md Phase 2 "calibration helper")."""

from __future__ import annotations

import time
from collections.abc import Callable

from golf_sim.audio.level import compute_level_db
from golf_sim.audio.source import AudioSource


def suggest_threshold_db(
    ambient_levels: list[float], impact_levels: list[float], margin_fraction: float = 0.5
) -> float:
    ambient_max = max(ambient_levels)
    impact_min = min(impact_levels)
    if impact_min <= ambient_max:
        raise ValueError(
            f"impact level ({impact_min:.1f} dB) doesn't clear ambient noise "
            f"({ambient_max:.1f} dB) -- move to a quieter room, check mic gain, "
            "or make a louder sample sound"
        )
    return ambient_max + (impact_min - ambient_max) * margin_fraction


def _record_levels(source: AudioSource, duration_s: float) -> list[float]:
    levels = []
    deadline = time.monotonic() + duration_s
    while time.monotonic() < deadline:
        block = source.read()
        if block is not None:
            levels.append(compute_level_db(block.samples))
    return levels


def run_calibration(
    source: AudioSource,
    ambient_duration_s: float = 3.0,
    num_impacts: int = 3,
    impact_window_s: float = 0.5,
    margin_fraction: float = 0.5,
    prompt: Callable[[str], None] = print,
    wait_for_user: Callable[[str], None] = input,
) -> float:
    source.open()
    try:
        prompt(f"Recording ambient noise for {ambient_duration_s:.0f}s -- stay quiet...")
        ambient_levels = _record_levels(source, ambient_duration_s)

        impact_levels = []
        for i in range(num_impacts):
            wait_for_user(f"Press Enter, then make impact sound {i + 1}/{num_impacts}...")
            prompt(f"Recording for {impact_window_s:.1f}s...")
            levels = _record_levels(source, impact_window_s)
            impact_levels.append(max(levels))

        threshold = suggest_threshold_db(ambient_levels, impact_levels, margin_fraction)
        prompt(f"Ambient max: {max(ambient_levels):.1f} dB")
        prompt(f"Impact samples: {[f'{lvl:.1f}' for lvl in impact_levels]} dB")
        prompt(f"Suggested threshold_db: {threshold:.1f}")
        return threshold
    finally:
        source.close()
