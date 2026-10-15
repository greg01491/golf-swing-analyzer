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

from dataclasses import asdict, dataclass, field

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
_KEYPOINT_CONFIDENCE_THRESHOLD = 0.6
_TRIANGULATION_CONFIDENCE_THRESHOLD = 0.3
_MIN_WRIST_VISIBILITY = 0.8


@dataclass
class TrackingQuality:
    moving_fraction: float  # share of frames with real (non-held) hand motion
    hand_vertical_range_m: float
    reliable: bool
    warnings: list[str]
    advisories: list[str] = field(default_factory=list)
    swing_moving_fraction: float | None = None
    camera_wrist_visibility: dict[str, dict[str, float]] | None = None
    camera_wrist_triangulation_coverage: dict[str, dict[str, float]] | None = None
    metric_confidence: dict[str, str] | None = None
    metric_reasons: dict[str, list[str]] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _hands(seq: LandmarkSequence) -> np.ndarray:
    return (seq.marker("RWrist") + seq.marker("LWrist")) / 2


def assess_tracking_quality(
    seq: LandmarkSequence,
    swing_window: tuple[int, int] | None = None,
    camera_wrist_visibility: dict[str, dict[str, float]] | None = None,
    camera_wrist_triangulation_coverage: dict[str, dict[str, float]] | None = None,
    metric_confidence: dict[str, str] | None = None,
    metric_reasons: dict[str, list[str]] | None = None,
) -> TrackingQuality:
    hands = _hands(seq)
    warnings: list[str] = []
    advisories: list[str] = []

    if seq.n_frames < 2:
        return TrackingQuality(0.0, 0.0, False, ["too few frames to analyse"])

    steps = np.linalg.norm(np.diff(hands, axis=0), axis=1)
    finite = steps[np.isfinite(steps)]
    moving_fraction = float((finite >= _FROZEN_STEP_M).mean()) if finite.size else 0.0
    swing_moving_fraction = None
    if swing_window is not None:
        start = max(0, min(swing_window))
        end = min(seq.n_frames - 1, max(swing_window))
        swing_steps = steps[start:end]
        swing_finite = swing_steps[np.isfinite(swing_steps)]
        if end > start and swing_finite.size:
            swing_moving_fraction = float((swing_finite >= _FROZEN_STEP_M).mean())

    vertical_range = float(np.nanmax(hands) - np.nanmin(hands))  # coarse, axis-agnostic

    measured_fraction = (
        swing_moving_fraction if swing_moving_fraction is not None else moving_fraction
    )
    if measured_fraction < _MIN_MOVING_FRACTION:
        percentage = measured_fraction * 100
        if swing_moving_fraction is None:
            warnings.append(
                f"Only {percentage:.0f}% of whole-clip hand steps showed motion; without "
                "address and impact frames, stationary lead-in and follow-through may affect "
                "this estimate. Positions and metrics may be unreliable."
            )
        else:
            warnings.append(
                f"Only {percentage:.0f}% of address-to-impact hand steps showed motion. "
                "The active swing may be gap-filled, so positions and metrics are unreliable."
            )

    if camera_wrist_triangulation_coverage is not None:
        for camera, wrists in camera_wrist_triangulation_coverage.items():
            for wrist, coverage in wrists.items():
                if coverage < _MIN_WRIST_VISIBILITY:
                    warnings.append(
                        f"{camera} {wrist} met Pose2Sim's triangulation confidence cutoff "
                        f"({_TRIANGULATION_CONFIDENCE_THRESHOLD:.1f}) in only "
                        f"{coverage * 100:.0f}% of address-to-impact frames; 3D tracking may "
                        "be gap-filled. Improve wrist visibility, framing, or lighting."
                    )

    if camera_wrist_visibility is not None:
        for camera, wrists in camera_wrist_visibility.items():
            for wrist, coverage in wrists.items():
                if coverage < _MIN_WRIST_VISIBILITY:
                    advisories.append(
                        f"{camera} {wrist} confidence was at least "
                        f"{_KEYPOINT_CONFIDENCE_THRESHOLD:.1f} in only {coverage * 100:.0f}% "
                        "of address-to-impact frames. This is a visibility advisory; Pose2Sim "
                        f"still accepts confidence at or above "
                        f"{_TRIANGULATION_CONFIDENCE_THRESHOLD:.1f}."
                    )

    if vertical_range > _MAX_PLAUSIBLE_HAND_RANGE_M:
        warnings.append(
            f"reconstructed hand travel ({vertical_range:.1f} m) is physically impossible "
            "-- the rig calibration looks wrong; recalibrate before trusting results"
        )

    if metric_confidence:
        for name in ("shoulder_turn_deg", "hip_turn_deg", "head_movement_cm"):
            if metric_confidence.get(name) == "unavailable":
                details = "; ".join((metric_reasons or {}).get(name, []))
                warnings.append(
                    f"{name} is unavailable: {details or 'required landmarks are unsupported'}"
                )
        estimated = [name for name, status in metric_confidence.items() if status == "estimated"]
        if estimated:
            advisories.append(
                "Estimated measurements have no target verdict or coaching: " + ", ".join(estimated)
            )

    return TrackingQuality(
        moving_fraction=round(moving_fraction, 3),
        hand_vertical_range_m=round(vertical_range, 2),
        reliable=not warnings,
        warnings=warnings,
        advisories=advisories,
        swing_moving_fraction=(
            None if swing_moving_fraction is None else round(swing_moving_fraction, 3)
        ),
        camera_wrist_visibility=camera_wrist_visibility,
        camera_wrist_triangulation_coverage=camera_wrist_triangulation_coverage,
        metric_confidence=metric_confidence,
        metric_reasons=metric_reasons,
    )
