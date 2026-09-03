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
from golf_sim.analysis.phases import SwingPhases, detect_phases, hands_midpoint
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


def _first_marker(seq: LandmarkSequence, *names: str) -> str | None:
    for name in names:
        if seq.has_marker(name):
            return name
    return None


def _joint_angle_series(seq: LandmarkSequence, a: str, b: str, c: str) -> np.ndarray:
    """Per-frame included angle (degrees) at joint ``b`` of the a-b-c chain."""
    va = seq.marker(a) - seq.marker(b)
    vc = seq.marker(c) - seq.marker(b)
    dots = np.sum(va * vc, axis=1)
    norms = np.linalg.norm(va, axis=1) * np.linalg.norm(vc, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos_angle = np.clip(dots / norms, -1.0, 1.0)
    return np.degrees(np.arccos(cos_angle))


def _stance_basis(
    seq: LandmarkSequence, phases: SwingPhases
) -> tuple[list[int], np.ndarray, np.ndarray] | None:
    """Horizontal reference frame at address, resolved to the target line.

    Returns ``(horizontal_axes, target_dir, ball_dir)`` where ``target_dir`` is
    the unit horizontal vector pointing at the target (lead foot for the given
    handedness) and ``ball_dir`` is perpendicular to it in the horizontal plane
    (toward/away from the ball line). Returns None if the stance is degenerate.
    """
    up_axis, _ = vertical_axis(seq)
    horizontal_axes = [i for i in range(3) if i != up_axis]
    addr = phases.address_frame
    r_ank = seq.marker("RAnkle")[addr, horizontal_axes]
    l_ank = seq.marker("LAnkle")[addr, horizontal_axes]
    stance = l_ank - r_ank  # right -> left foot
    width = float(np.linalg.norm(stance))
    if width <= 0:
        return None
    target_dir = stance / width  # lead foot is the target side (assumed right-handed)
    ball_dir = np.array([-target_dir[1], target_dir[0]])
    return horizontal_axes, target_dir, ball_dir


def _lateral_spine_tilt(
    seq: LandmarkSequence, stance_dir: np.ndarray, horizontal_axes: list[int]
) -> np.ndarray:
    """Per-frame side-bend (degrees) of the hip->neck line toward the stance
    (frontal-plane) direction, signed relative to vertical."""
    up_axis, up_sign = vertical_axis(seq)
    spine = seq.marker("Neck") - seq.marker("Hip")
    up_component = spine[:, up_axis] * up_sign
    lateral = spine[:, horizontal_axes] @ stance_dir
    return np.degrees(np.arctan2(lateral, up_component))


def _peak_wrist_speed(seq: LandmarkSequence, frame: int) -> float:
    """Fastest wrist speed (m/s) in a ~0.1s window around ``frame``."""
    fps = seq.fps
    if fps <= 0 or seq.n_frames < 2:
        return float("nan")
    window = max(2, int(0.1 * fps))
    best = float("nan")
    for wrist in ("LWrist", "RWrist"):
        if not seq.has_marker(wrist):
            continue
        speed = np.linalg.norm(np.diff(seq.marker(wrist), axis=0), axis=1) * fps
        lo = max(0, frame - window)
        hi = min(len(speed), frame + window + 1)
        if hi <= lo:
            continue
        seg = speed[lo:hi]
        seg_max = float(np.nanmax(seg)) if np.isfinite(seg).any() else float("nan")
        if np.isfinite(seg_max) and (not np.isfinite(best) or seg_max > best):
            best = seg_max
    return best


def compute_metrics(
    seq: LandmarkSequence,
    metrics_config: MetricsConfig,
    phases: SwingPhases | None = None,
    handedness: str = "right",
) -> MetricsReport:
    if phases is None:
        phases = detect_phases(seq)

    address, top, impact = phases.address_frame, phases.top_frame, phases.impact_frame
    shoulder_turn = horizontal_angle_series(seq, "LShoulder", "RShoulder", address)
    hip_turn = horizontal_angle_series(seq, "LHip", "RHip", address)
    backswing = slice(address, top + 1)

    spine_tilt = _spine_tilt_series(seq)
    sway_top, sway_impact = _hip_sway_pct(seq, phases)

    up_axis, up_sign = vertical_axis(seq)
    horizontal_axes = [i for i in range(3) if i != up_axis]

    values: dict[str, tuple[float, str]] = {
        "shoulder_turn_deg": (float(np.nanmax(np.abs(shoulder_turn[backswing]))), "deg"),
        "hip_turn_deg": (float(np.nanmax(np.abs(hip_turn[backswing]))), "deg"),
        "x_factor_deg": (
            float(np.nanmax(np.abs(shoulder_turn[backswing] - hip_turn[backswing]))),
            "deg",
        ),
        "spine_tilt_deg": (float(spine_tilt[address]), "deg"),
        "tempo_ratio": (phases.tempo_ratio(seq.times), "ratio"),
        "hip_sway_top_pct": (sway_top, "% stance width"),
        "hip_sway_impact_pct": (sway_impact, "% stance width"),
    }

    # --- Rotation & sequencing -------------------------------------------
    values["hip_rotation_impact_deg"] = (float(abs(hip_turn[impact])), "deg")
    values["backswing_time_s"] = (float(seq.times[top] - seq.times[address]), "s")
    values["downswing_time_s"] = (float(seq.times[impact] - seq.times[top]), "s")

    # Secondary-axis (shoulder) tilt at impact: how far the shoulder line is
    # lifted out of horizontal (trail shoulder drops below lead at impact).
    shoulder_line = seq.marker("RShoulder") - seq.marker("LShoulder")
    sh_up = np.abs(shoulder_line[:, up_axis])
    sh_horiz = np.linalg.norm(shoulder_line[:, horizontal_axes], axis=1)
    shoulder_tilt = np.degrees(np.arctan2(sh_up, sh_horiz))
    values["shoulder_tilt_impact_deg"] = (float(shoulder_tilt[impact]), "deg")

    # --- Posture & stability ---------------------------------------------
    values["spine_angle_change_deg"] = (
        float(abs(spine_tilt[impact] - spine_tilt[address])),
        "deg",
    )

    head_name = _first_marker(seq, "Head", "Nose", "Neck")
    if head_name is not None:
        head = seq.marker(head_name)
        values["head_movement_cm"] = (
            float(np.linalg.norm(head[impact] - head[address]) * 100),
            "cm",
        )

    basis = _stance_basis(seq, phases)
    if basis is not None:
        h_axes, target_dir, ball_dir = basis
        # Early extension: pelvis drift toward/away the ball line, address->impact.
        hip_h = seq.marker("Hip")[:, h_axes]
        hip_move = hip_h[impact] - hip_h[address]
        values["early_extension_cm"] = (float(abs(hip_move @ ball_dir) * 100), "cm")
        # Reverse spine: lateral spine side-bend at the top of the backswing.
        lateral_tilt = _lateral_spine_tilt(seq, target_dir, h_axes)
        values["reverse_spine_deg"] = (float(abs(lateral_tilt[top])), "deg")

    # --- Body angles & speed proxies -------------------------------------
    knee_angles = []
    for hip_m, knee_m, ankle_m in (("LHip", "LKnee", "LAnkle"), ("RHip", "RKnee", "RAnkle")):
        if seq.has_marker(knee_m) and seq.has_marker(hip_m) and seq.has_marker(ankle_m):
            knee_angles.append(_joint_angle_series(seq, hip_m, knee_m, ankle_m)[address])
    if knee_angles:
        finite = [a for a in knee_angles if np.isfinite(a)]
        values["knee_flex_deg"] = (
            float(np.mean(finite)) if finite else float("nan"),
            "deg",
        )

    lead = "L" if handedness == "right" else "R"
    sh_m, el_m, wr_m = f"{lead}Shoulder", f"{lead}Elbow", f"{lead}Wrist"
    if seq.has_marker(el_m):
        lead_arm = _joint_angle_series(seq, sh_m, el_m, wr_m)
        values["lead_arm_deg"] = (float(lead_arm[top]), "deg")

    values["hand_speed_impact_ms"] = (_peak_wrist_speed(seq, impact), "m/s")

    # Swing-plane proxy: inclination of the hand path from address to the top.
    hands = hands_midpoint(seq)
    path = hands[top] - hands[address]
    path_up = path[up_axis] * up_sign
    path_horiz = float(np.linalg.norm(path[horizontal_axes]))
    values["swing_plane_deg"] = (float(np.degrees(np.arctan2(path_up, path_horiz))), "deg")

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
