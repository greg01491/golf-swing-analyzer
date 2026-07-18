"""Builds a "ghost" reference skeleton per P-position, so the review UI can
overlay "where you should be" against "where you actually were".

The ghost is built from the golfer's OWN measured body proportions (arm
lengths, shoulder/hip width, all measured at address) posed into target
rotation/arm-elevation angles -- not a generic mannequin. It deliberately
only idealizes what the P-system checkpoints are actually about: shoulder
turn, hip turn, and lead-arm carriage. Spine posture, stance, and leg
position are copied from the golfer's real frame unchanged, since idealizing
those isn't what P-positions check and would make the overlay fight the
real footage instead of complementing it.

Target angles are approximations -- see comments below -- calibrated as
fractions of the golfer's own configured reference ranges (metrics.
reference_ranges), not literal club-shaft measurements (no club tracking;
spec.md NG2). This is a v1: the fractions encode reasonable, commonly
taught checkpoints but are not derived from biomechanical study.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from golf_sim.analysis.frame_of_reference import horizontal_angle_series, vertical_axis
from golf_sim.analysis.p_positions import Handedness, lead_markers
from golf_sim.analysis.phases import SwingPhases
from golf_sim.config import MetricsConfig
from golf_sim.trc import LandmarkSequence

# (shoulder_turn_fraction, hip_turn_fraction, lead_arm_elevation_deg or None)
# Fraction multiplies the configured shoulder/hip_turn_deg reference-range
# midpoint, signed to match whichever rotation direction the actual swing
# shows (so it works regardless of handedness/camera orientation). None for
# P1 means "don't idealize the arm -- address is the baseline, not a target".
_TARGETS: dict[str, tuple[float, float, float | None]] = {
    "P1": (0.0, 0.0, None),
    "P2": (0.3, 0.2, -45.0),
    "P3": (0.6, 0.4, 0.0),
    "P4": (1.0, 1.0, 20.0),
    "P5": (0.6, 0.3, 0.0),
    "P6": (0.2, 0.1, -45.0),
    "P7": (0.0, -0.15, -45.0),
    "P8": (-0.2, -0.3, -45.0),
    "P9": (-0.6, -0.5, 0.0),
    "P10": (-0.9, -0.8, 60.0),
}


@dataclass
class BodyProportions:
    up_axis: int
    up_sign: float
    shoulder_line_address: np.ndarray  # RShoulder - LShoulder, horizontal component, at address
    hip_line_address: np.ndarray  # RHip - LHip, horizontal component, at address
    lead_upper_arm_len: float
    lead_forearm_len: float
    trail_upper_arm_len: float
    trail_forearm_len: float


def _horizontal_only(vec: np.ndarray, up_axis: int) -> np.ndarray:
    out = vec.copy()
    out[up_axis] = 0.0
    return out


def _rotate_in_horizontal_plane(vec: np.ndarray, up_axis: int, angle_deg: float) -> np.ndarray:
    """Rotates a vector's horizontal-plane component by angle_deg, with the
    same sign convention as frame_of_reference.horizontal_angle_series (so a
    target of X degrees measured back with that function reads back as X)."""
    horizontal_axes = [i for i in range(3) if i != up_axis]
    theta = np.radians(angle_deg)
    u, v = vec[horizontal_axes[0]], vec[horizontal_axes[1]]
    out = vec.copy()
    out[horizontal_axes[0]] = u * np.cos(theta) - v * np.sin(theta)
    out[horizontal_axes[1]] = u * np.sin(theta) + v * np.cos(theta)
    return out


def measure_proportions(
    seq: LandmarkSequence, address_frame: int, handedness: Handedness
) -> BodyProportions:
    up_axis, up_sign = vertical_axis(seq)
    lead_shoulder, lead_wrist = lead_markers(handedness)
    trail_shoulder, trail_wrist = (
        ("RShoulder", "RWrist")
        if handedness == "right"
        else (
            "LShoulder",
            "LWrist",
        )
    )
    lead_elbow = "LElbow" if lead_shoulder == "LShoulder" else "RElbow"
    trail_elbow = "RElbow" if trail_shoulder == "RShoulder" else "LElbow"

    shoulder_line = seq.marker("RShoulder")[address_frame] - seq.marker("LShoulder")[address_frame]
    hip_line = seq.marker("RHip")[address_frame] - seq.marker("LHip")[address_frame]

    def seg_len(a: str, b: str) -> float:
        return float(np.linalg.norm(seq.marker(b)[address_frame] - seq.marker(a)[address_frame]))

    return BodyProportions(
        up_axis=up_axis,
        up_sign=up_sign,
        shoulder_line_address=_horizontal_only(shoulder_line, up_axis),
        hip_line_address=_horizontal_only(hip_line, up_axis),
        lead_upper_arm_len=seg_len(lead_shoulder, lead_elbow),
        lead_forearm_len=seg_len(lead_elbow, lead_wrist),
        trail_upper_arm_len=seg_len(trail_shoulder, trail_elbow),
        trail_forearm_len=seg_len(trail_elbow, trail_wrist),
    )


def build_ideal_frame(
    seq: LandmarkSequence,
    frame_idx: int,
    shoulder_turn_deg: float,
    hip_turn_deg: float,
    arm_elevation_deg: float | None,
    handedness: Handedness,
    proportions: BodyProportions,
) -> dict[str, np.ndarray]:
    """Returns {marker_name: xyz} for every marker in seq, with shoulders/
    hips/lead-arm idealized and everything else copied from the real frame."""
    up_axis, up_sign = proportions.up_axis, proportions.up_sign
    out: dict[str, np.ndarray] = {
        name: seq.marker(name)[frame_idx].copy() for name in seq.marker_names
    }

    shoulder_center = (seq.marker("LShoulder")[frame_idx] + seq.marker("RShoulder")[frame_idx]) / 2
    hip_center = seq.marker("Hip")[frame_idx]

    ideal_shoulder_line = _rotate_in_horizontal_plane(
        proportions.shoulder_line_address, up_axis, shoulder_turn_deg
    )
    ideal_hip_line = _rotate_in_horizontal_plane(
        proportions.hip_line_address, up_axis, hip_turn_deg
    )
    out["RShoulder"] = shoulder_center + ideal_shoulder_line / 2
    out["LShoulder"] = shoulder_center - ideal_shoulder_line / 2
    out["RHip"] = hip_center + ideal_hip_line / 2
    out["LHip"] = hip_center - ideal_hip_line / 2

    if arm_elevation_deg is None:
        return out  # P1: arms stay at their actual (address) position

    lead_shoulder_name, lead_wrist_name = lead_markers(handedness)
    lead_elbow_name = "LElbow" if lead_shoulder_name == "LShoulder" else "RElbow"
    trail_shoulder_name = "RShoulder" if lead_shoulder_name == "LShoulder" else "LShoulder"
    trail_elbow_name = "RElbow" if lead_elbow_name == "LElbow" else "LElbow"
    trail_wrist_name = "RWrist" if lead_wrist_name == "LWrist" else "LWrist"

    actual_vec = seq.marker(lead_wrist_name)[frame_idx] - seq.marker(lead_shoulder_name)[frame_idx]
    horiz = _horizontal_only(actual_vec, up_axis)
    horiz_norm = np.linalg.norm(horiz)
    if horiz_norm < 1e-6:
        # degenerate (arm pointing straight up/down): fall back to the
        # shoulder line's perpendicular as a plausible swing-plane direction
        horiz = _rotate_in_horizontal_plane(proportions.shoulder_line_address, up_axis, 90.0)
        horiz_norm = np.linalg.norm(horiz) or 1.0
    horiz_unit = horiz / horiz_norm
    vertical_unit = np.zeros(3)
    vertical_unit[up_axis] = up_sign

    elevation_rad = np.radians(arm_elevation_deg)
    direction = np.cos(elevation_rad) * horiz_unit + np.sin(elevation_rad) * vertical_unit

    lead_shoulder_pos = out[lead_shoulder_name]
    lead_arm_len = proportions.lead_upper_arm_len + proportions.lead_forearm_len
    out[lead_wrist_name] = lead_shoulder_pos + direction * lead_arm_len
    out[lead_elbow_name] = lead_shoulder_pos + direction * proportions.lead_upper_arm_len

    # Trail arm: both hands are on the same grip in real golf, so aim the
    # trail wrist at the same point as the lead wrist rather than giving it
    # its own (unmeasured) elevation target.
    trail_shoulder_pos = out[trail_shoulder_name]
    to_grip = out[lead_wrist_name] - trail_shoulder_pos
    to_grip_len = np.linalg.norm(to_grip) or 1.0
    trail_unit = to_grip / to_grip_len
    out[trail_wrist_name] = out[lead_wrist_name]
    out[trail_elbow_name] = trail_shoulder_pos + trail_unit * proportions.trail_upper_arm_len

    return out


def _target_midpoint(metrics_config: MetricsConfig, key: str, default: float) -> float:
    ref = metrics_config.reference_ranges.get(key)
    return default if ref is None else (ref.min + ref.max) / 2


def build_all_ideal_frames(
    seq: LandmarkSequence,
    phases: SwingPhases,
    p_position_frames: dict[str, int],
    metrics_config: MetricsConfig,
    handedness: Handedness = "right",
) -> dict[str, dict[str, np.ndarray]]:
    """{P-position name: {marker_name: xyz}} for every detected P-position."""
    proportions = measure_proportions(seq, phases.address_frame, handedness)
    shoulder_mid = _target_midpoint(metrics_config, "shoulder_turn_deg", default=90.0)
    hip_mid = _target_midpoint(metrics_config, "hip_turn_deg", default=45.0)

    backswing_sign = float(
        np.sign(
            horizontal_angle_series(seq, "LShoulder", "RShoulder", phases.address_frame)[
                phases.top_frame
            ]
        )
    )
    if backswing_sign == 0:
        backswing_sign = 1.0

    frames: dict[str, dict[str, np.ndarray]] = {}
    for name, frame_idx in p_position_frames.items():
        shoulder_frac, hip_frac, elevation = _TARGETS[name]
        frames[name] = build_ideal_frame(
            seq,
            frame_idx,
            shoulder_turn_deg=shoulder_frac * shoulder_mid * backswing_sign,
            hip_turn_deg=hip_frac * hip_mid * backswing_sign,
            arm_elevation_deg=elevation,
            handedness=handedness,
            proportions=proportions,
        )
    return frames
