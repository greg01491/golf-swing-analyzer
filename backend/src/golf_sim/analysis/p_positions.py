"""Detects the 10 checkpoints of golf's "P-System" (P1 Address through P10
Finish, popularized by Mac O'Grady) from the 3D landmark sequence.

The textbook P-system is defined by CLUB positions (shaft parallel to the
ground, etc.) -- but club tracking is explicitly out of scope for this
project (spec.md NG2). Instead these are approximated from body pose alone,
using two measurable proxies for the same checkpoints:

- "club shaft parallel to ground" (P2/P6/P8) -> the hands cross the
  golfer's own hip height, since a level club held at address-length arms
  puts the hands roughly there.
- "lead arm parallel to ground" (P3/P5/P9) -> the lead shoulder-to-wrist
  vector crosses horizontal (0 degrees elevation).

Both are genuine geometric proxies, not arbitrary guesses, but they are
still approximations -- documented as such wherever this shows up (tips,
UI). P1/P4/P7 reuse the existing address/top/impact phase detection, and
P10 is the peak hand height after P9 (mirrors "top" on the finish side).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from golf_sim.analysis.frame_of_reference import vertical_axis
from golf_sim.analysis.phases import SwingPhases, hands_midpoint
from golf_sim.trc import LandmarkSequence

Handedness = Literal["right", "left"]

# (name, label)
_POSITIONS: list[tuple[str, str]] = [
    ("P1", "Address"),
    ("P2", "Takeaway"),
    ("P3", "Halfway Back"),
    ("P4", "Top of Backswing"),
    ("P5", "Early Downswing"),
    ("P6", "Pre-Impact"),
    ("P7", "Impact"),
    ("P8", "Release"),
    ("P9", "Follow-Through"),
    ("P10", "Finish"),
]


@dataclass
class PPosition:
    name: str
    label: str
    frame_index: int
    time_s: float
    available: bool = True
    unavailable_reason: str | None = None


def lead_markers(handedness: Handedness) -> tuple[str, str]:
    """(shoulder, wrist) marker names for the lead arm (nearer the target)."""
    return ("LShoulder", "LWrist") if handedness == "right" else ("RShoulder", "RWrist")


def arm_elevation_series(seq: LandmarkSequence, shoulder: str, wrist: str) -> np.ndarray:
    """Per-frame angle (degrees) of the shoulder->wrist vector from
    horizontal: 0 = parallel to the ground, +90 = straight up, -90 = straight
    down."""
    up_axis, up_sign = vertical_axis(seq)
    horizontal_axes = [i for i in range(3) if i != up_axis]
    vec = seq.marker(wrist) - seq.marker(shoulder)
    vertical = vec[:, up_axis] * up_sign
    horizontal = np.linalg.norm(vec[:, horizontal_axes], axis=1)
    return np.degrees(np.arctan2(vertical, horizontal))


def _closest_to_zero(series: np.ndarray, start: int, end: int) -> int:
    lo, hi = min(start, end), max(start, end)
    return lo + int(np.nanargmin(np.abs(series[lo : hi + 1])))


def _find_crossing(series: np.ndarray, start: int, end: int) -> tuple[int, bool]:
    """First zero-crossing of series within [start, end]; falls back to the
    closest-to-zero frame for diagnostics when the series never actually
    crosses. The fallback is not a detected checkpoint and must not be offered
    for navigation as though the proxy target were observed."""
    lo, hi = min(start, end), max(start, end)
    if hi <= lo:
        return lo, bool(np.isfinite(series[lo]) and series[lo] == 0)
    segment = series[lo : hi + 1]
    signs = np.sign(segment)
    for i in range(1, len(segment)):
        if signs[i] == 0:
            return lo + i, True
        if signs[i - 1] != 0 and signs[i - 1] != signs[i]:
            a, b = lo + i - 1, lo + i
            return (a if abs(series[a]) < abs(series[b]) else b), True
    return _closest_to_zero(series, lo, hi), False


def detect_p_positions(
    seq: LandmarkSequence, phases: SwingPhases, handedness: Handedness = "right"
) -> list[PPosition]:
    up_axis, up_sign = vertical_axis(seq)
    shoulder, wrist = lead_markers(handedness)

    hand_height = hands_midpoint(seq)[:, up_axis] * up_sign
    hip_height_ref = float(seq.marker("Hip")[phases.address_frame, up_axis] * up_sign)
    elevation = arm_elevation_series(seq, shoulder, wrist)

    p1 = phases.address_frame
    p4 = phases.top_frame
    p7 = phases.impact_frame

    p3, p3_crossed = _find_crossing(elevation, p1, p4)
    p2, p2_crossed = _find_crossing(hand_height - hip_height_ref, p1, p3)

    p5, p5_crossed = _find_crossing(elevation, p4, p7)
    p6, p6_crossed = _find_crossing(hand_height - hip_height_ref, p5, p7)

    # P10 (finish): peak hand height after impact, mirroring "top" on the
    # follow-through side; search the whole post-impact tail since P9 isn't
    # known yet at this point.
    if p7 >= seq.n_frames - 1:
        p10 = p7
    else:
        p10 = p7 + int(np.nanargmax(hand_height[p7:]))

    p9, p9_crossed = _find_crossing(elevation, p7, p10)
    p8, p8_crossed = _find_crossing(hand_height - hip_height_ref, p7, p9)

    frames = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10]
    available = [
        True,
        p2_crossed and p3_crossed,
        p3_crossed,
        True,
        p5_crossed and p6_crossed,
        p5_crossed and p6_crossed,
        True,
        p8_crossed and p9_crossed,
        p9_crossed,
        True,
    ]
    # Reserve phase anchors so proxy estimates cannot move P4 or P7. Within
    # each interval, clamp estimates to distinct interior frames and mark any
    # estimate moved by the correction unavailable for review.
    last = seq.n_frames - 1
    for start_index, end_index in ((0, 3), (3, 6), (6, 9)):
        start_frame, end_frame = frames[start_index], min(frames[end_index], last)
        required_gap = end_index - start_index
        if end_frame - start_frame < required_gap:
            for index in range(start_index + 1, end_index):
                frames[index] = min(start_frame + index - start_index, last)
                available[index] = False
            available[end_index] = False
            continue

        previous = start_frame
        for index in range(start_index + 1, end_index):
            original = frames[index]
            latest = end_frame - (end_index - index)
            frames[index] = min(max(original, previous + 1), latest)
            if frames[index] != original:
                available[index] = False
            previous = frames[index]

    if frames[9] <= frames[8]:
        available[9] = False
        frames[9] = min(frames[8] + 1, last)

    return [
        PPosition(
            name=name,
            label=label,
            frame_index=frame,
            time_s=float(seq.times[frame]),
            available=was_detected,
            unavailable_reason=None if was_detected else "proxy target was not observed",
        )
        for (name, label), frame, was_detected in zip(_POSITIONS, frames, available, strict=True)
    ]
