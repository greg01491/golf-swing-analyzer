"""Swing phase detection from the 3D landmark sequence.

Finds three anchor frames from the hand (wrist midpoint) trajectory:

- address: the last quiet frame before the hands start moving
- top:     highest hand position between address and the end of the clip
- impact:  lowest hand position after the top (hands return to the ball,
           then rise again into the follow-through)

Heuristics deliberately use only relative quantities (fractions of peak
speed, per-clip min/max heights) so they're invariant to units, frame rate,
and where the golfer stands.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from golf_sim.analysis.frame_of_reference import vertical_axis
from golf_sim.trc import LandmarkSequence


class PhaseDetectionError(RuntimeError):
    pass


@dataclass
class SwingPhases:
    address_frame: int
    top_frame: int
    impact_frame: int

    def tempo_ratio(self, times: np.ndarray) -> float:
        backswing = times[self.top_frame] - times[self.address_frame]
        downswing = times[self.impact_frame] - times[self.top_frame]
        if downswing <= 0:
            raise PhaseDetectionError("impact not after top -- phase detection failed")
        return float(backswing / downswing)


def hands_midpoint(seq: LandmarkSequence) -> np.ndarray:
    return (seq.marker("RWrist") + seq.marker("LWrist")) / 2


def _rolling_median(x: np.ndarray, window: int = 5) -> np.ndarray:
    """Median filter that ignores NaNs; robust to single-frame outliers."""
    n = len(x)
    half = window // 2
    out = np.empty(n)
    for i in range(n):
        seg = x[max(0, i - half) : min(n, i + half + 1)]
        seg = seg[np.isfinite(seg)]
        out[i] = np.median(seg) if seg.size else np.nan
    return out


def detect_phases(
    seq: LandmarkSequence,
    quiet_speed_fraction: float = 0.1,
    impact_hint_frame: int | None = None,
) -> SwingPhases:
    if seq.n_frames < 5:
        raise PhaseDetectionError(f"too few frames ({seq.n_frames}) to detect phases")

    hands = hands_midpoint(seq)
    up_axis, up_sign = vertical_axis(seq)
    # A rolling median kills single-frame triangulation spikes (one badly
    # triangulated frame would otherwise become a false "lowest"/"highest"
    # hand position and wreck impact/top detection) while preserving the
    # real swing shape.
    height = _rolling_median(hands[:, up_axis] * up_sign, window=5)

    speed = np.linalg.norm(np.diff(hands, axis=0), axis=1) * seq.fps
    peak_speed = np.nanmax(speed)
    if not np.isfinite(peak_speed) or peak_speed <= 0:
        raise PhaseDetectionError("hands never move -- not a swing")

    moving = speed > quiet_speed_fraction * peak_speed
    first_move = int(np.argmax(moving))
    if not moving.any():
        raise PhaseDetectionError("no motion above quiet threshold")
    address = max(first_move - 1, 0)

    # Anchor on IMPACT. The audio trigger fires AT impact, so the clip is
    # built with impact at pre_capture_delay into it -- impact_hint_frame.
    # That's far more reliable than inferring it from geometry: hands are low
    # at BOTH address and impact, so a global "lowest hands" can't tell them
    # apart, and the finish is often higher than the backswing top so a
    # global "highest hands" grabs P10 instead of P4. Given the impact anchor,
    # we then look for the top only before it.
    if impact_hint_frame is not None:
        w = max(2, int(0.25 * seq.fps))  # refine within ±0.25s of the trigger
        lo = max(address + 1, impact_hint_frame - w)
        hi = min(seq.n_frames, impact_hint_frame + w + 1)
        impact = (
            lo + int(np.nanargmin(height[lo:hi]))
            if hi > lo
            else min(max(impact_hint_frame, address + 1), seq.n_frames - 1)
        )
    else:
        # no trigger anchor (manual capture / tests): fall back to lowest
        # hands after address
        tail = height[address + 1 :]
        if tail.size == 0:
            raise PhaseDetectionError("no frames after address -- clip too short")
        impact = address + 1 + int(np.nanargmin(tail))
    if impact <= address + 1:
        raise PhaseDetectionError("impact not clearly after address -- unclear swing")

    # Top of backswing = highest hands strictly BEFORE impact.
    top = address + int(np.nanargmax(height[address:impact]))
    if top <= address:
        top = min(address + 1, impact - 1)

    return SwingPhases(address_frame=address, top_frame=top, impact_frame=impact)
