"""Tracking-quality assessment for a reconstructed swing.

The 3D reconstruction quality varies a lot per capture: when the golfer isn't
confidently triangulated in both camera views (self-occlusion in the
down-the-line/face-on rig, poor lighting, partial framing), Pose2Sim fills
the gaps by holding the last valid value -- producing long "frozen" runs and,
if the calibration/scale is off, physically impossible coordinate ranges.

Phase detection and P-positions computed on such data are confidently wrong,
which is worse than saying nothing. This module scores the reconstruction so
the analysis can flag a low-confidence swing in the UI instead of presenting
garbage checkpoints as fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from golf_sim.trc import LandmarkSequence

# A full swing's hands trace a large 3D arc (address low -> top high & behind
# -> impact low -> finish high & around), so the bounding-box span can be
# ~3m on a *good* capture; only clearly-broken triangulations (seen: 5-8m)
# exceed this. Set generously to avoid false "impossible" flags on real swings.
_MAX_PLAUSIBLE_HAND_RANGE_M = 4.5
# Below this "real motion" fraction the sequence is mostly gap-filled and any
# derived phase/checkpoint is unreliable.
_MIN_MOVING_FRACTION = 0.6
_FROZEN_STEP_M = 0.001  # <1mm between frames == a held (gap-filled) value


@dataclass
class TrackingQuality:
    moving_fraction: float  # share of frames with real (non-held) hand motion
    hand_vertical_range_m: float
    reliable: bool
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _hands(seq: LandmarkSequence) -> np.ndarray:
    return (seq.marker("RWrist") + seq.marker("LWrist")) / 2


def assess_tracking_quality(seq: LandmarkSequence) -> TrackingQuality:
    hands = _hands(seq)
    warnings: list[str] = []

    if seq.n_frames < 2:
        return TrackingQuality(0.0, 0.0, False, ["too few frames to analyse"])

    steps = np.linalg.norm(np.diff(hands, axis=0), axis=1)
    finite = steps[np.isfinite(steps)]
    moving_fraction = float((finite >= _FROZEN_STEP_M).mean()) if finite.size else 0.0

    vertical_range = float(np.nanmax(hands) - np.nanmin(hands))  # coarse, axis-agnostic

    if moving_fraction < _MIN_MOVING_FRACTION:
        warnings.append(
            f"{(1 - moving_fraction) * 100:.0f}% of frames were estimated (the golfer "
            "couldn't be tracked in both cameras) -- positions and metrics are unreliable"
        )
    if vertical_range > _MAX_PLAUSIBLE_HAND_RANGE_M:
        warnings.append(
            f"reconstructed hand travel ({vertical_range:.1f} m) is physically impossible "
            "-- the rig calibration looks wrong; recalibrate before trusting results"
        )

    return TrackingQuality(
        moving_fraction=round(moving_fraction, 3),
        hand_vertical_range_m=round(vertical_range, 2),
        reliable=not warnings,
        warnings=warnings,
    )
