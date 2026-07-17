"""Swing metric computations from the 3D landmark sequence (FR16/FR17).

All angles are reported as magnitudes (degrees) so they're neutral to
handedness and to which way the calibrated axes point. Reference ranges come
from config.yaml (metrics.reference_ranges) and are user-editable; a metric
with no configured range is reported unflagged.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from golf_sim.analysis.frame_of_reference import horizontal_angle_series, vertical_axis
from golf_sim.analysis.phases import SwingPhases, detect_phases
from golf_sim.config import MetricsConfig
from golf_sim.trc import LandmarkSequence


@dataclass
class MetricResult:
    name: str
    value: float
    unit: str
    in_range: bool | None  # None = no reference range configured
    range_min: float | None
    range_max: float | None


@dataclass
class MetricsReport:
    phases: SwingPhases
    metrics: list[MetricResult]

    def to_dict(self) -> dict:
        return {
            "phases": {
                "address_frame": self.phases.address_frame,
                "top_frame": self.phases.top_frame,
                "impact_frame": self.phases.impact_frame,
            },
            "metrics": [
                {
                    "name": m.name,
                    "value": round(m.value, 2),
                    "unit": m.unit,
                    "in_range": m.in_range,
                    "range": (
                        None if m.range_min is None else {"min": m.range_min, "max": m.range_max}
                    ),
                }
                for m in self.metrics
            ],
        }


def _spine_tilt_series(seq: LandmarkSequence) -> np.ndarray:
    """Per-frame angle (degrees) of the hip->neck line from vertical."""
    up_axis, up_sign = vertical_axis(seq)
    spine = seq.marker("Neck") - seq.marker("Hip")
    vertical_component = spine[:, up_axis] * up_sign
    norms = np.linalg.norm(spine, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos_angle = np.clip(vertical_component / norms, -1.0, 1.0)
    return np.degrees(np.arccos(cos_angle))


def _hip_sway_pct(seq: LandmarkSequence, phases: SwingPhases) -> tuple[float, float]:
    """Lateral hip-center displacement at top and impact, relative to
    address, as a percentage of stance width. Positive = away from the
    direction the hips moved... sign is not handedness-resolved, so we
    report magnitudes and leave direction interpretation to the tips layer.
    """
    up_axis, _ = vertical_axis(seq)
    horizontal_axes = [i for i in range(3) if i != up_axis]

    hip = seq.marker("Hip")[:, horizontal_axes]
    r_ankle = seq.marker("RAnkle")[phases.address_frame, horizontal_axes]
    l_ankle = seq.marker("LAnkle")[phases.address_frame, horizontal_axes]
    stance_line = r_ankle - l_ankle
    stance_width = float(np.linalg.norm(stance_line))
    if stance_width <= 0:
        return float("nan"), float("nan")
    stance_dir = stance_line / stance_width

    hip_rel = hip - hip[phases.address_frame]
    sway = hip_rel @ stance_dir  # component along the stance line
    return (
        float(abs(sway[phases.top_frame]) / stance_width * 100),
        float(abs(sway[phases.impact_frame]) / stance_width * 100),
    )


def compute_metrics(
    seq: LandmarkSequence,
    metrics_config: MetricsConfig,
    phases: SwingPhases | None = None,
) -> MetricsReport:
    if phases is None:
        phases = detect_phases(seq)

    shoulder_turn = horizontal_angle_series(seq, "LShoulder", "RShoulder", phases.address_frame)
    hip_turn = horizontal_angle_series(seq, "LHip", "RHip", phases.address_frame)
    backswing = slice(phases.address_frame, phases.top_frame + 1)

    spine_tilt = _spine_tilt_series(seq)
    sway_top, sway_impact = _hip_sway_pct(seq, phases)

    values: dict[str, tuple[float, str]] = {
        "shoulder_turn_deg": (float(np.nanmax(np.abs(shoulder_turn[backswing]))), "deg"),
        "hip_turn_deg": (float(np.nanmax(np.abs(hip_turn[backswing]))), "deg"),
        "x_factor_deg": (
            float(np.nanmax(np.abs(shoulder_turn[backswing] - hip_turn[backswing]))),
            "deg",
        ),
        "spine_tilt_deg": (float(spine_tilt[phases.address_frame]), "deg"),
        "tempo_ratio": (phases.tempo_ratio(seq.times), "ratio"),
        "hip_sway_top_pct": (sway_top, "% stance width"),
        "hip_sway_impact_pct": (sway_impact, "% stance width"),
    }

    results = []
    for name, (value, unit) in values.items():
        ref = metrics_config.reference_ranges.get(name)
        if ref is None or not np.isfinite(value):
            in_range, lo, hi = None, None, None
        else:
            lo, hi = ref.min, ref.max
            in_range = bool(lo <= value <= hi)
        results.append(
            MetricResult(
                name=name, value=value, unit=unit, in_range=in_range, range_min=lo, range_max=hi
            )
        )
    return MetricsReport(phases=phases, metrics=results)
