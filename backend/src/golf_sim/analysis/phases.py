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


def detect_phases(seq: LandmarkSequence, quiet_speed_fraction: float = 0.1) -> SwingPhases:
    if seq.n_frames < 5:
        raise PhaseDetectionError(f"too few frames ({seq.n_frames}) to detect phases")

    hands = hands_midpoint(seq)
    up_axis, up_sign = vertical_axis(seq)
    height = hands[:, up_axis] * up_sign

    speed = np.linalg.norm(np.diff(hands, axis=0), axis=1) * seq.fps
    peak_speed = np.nanmax(speed)
    if not np.isfinite(peak_speed) or peak_speed <= 0:
        raise PhaseDetectionError("hands never move -- not a swing")

    moving = speed > quiet_speed_fraction * peak_speed
    first_move = int(np.argmax(moving))
    if not moving.any():
        raise PhaseDetectionError("no motion above quiet threshold")
    address = max(first_move - 1, 0)

    top = address + int(np.nanargmax(height[address:]))
    if top >= seq.n_frames - 1:
        raise PhaseDetectionError(
            "top of backswing is the last frame -- clip appears to end mid-backswing"
        )
    impact = top + int(np.nanargmin(height[top:]))
    if impact == top:
        raise PhaseDetectionError("no downswing found after top of backswing")

    return SwingPhases(address_frame=address, top_frame=top, impact_frame=impact)
