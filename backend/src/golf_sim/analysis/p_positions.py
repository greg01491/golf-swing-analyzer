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

from golf_sim.analysis.frame_of_reference import AnalysisReference, infer_reference
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
    detected: bool = True
    estimate_reason: str | None = None
    unavailable_reason: str | None = None


def lead_markers(handedness: Handedness) -> tuple[str, str]:
    """(shoulder, wrist) marker names for the lead arm (nearer the target)."""
    return ("LShoulder", "LWrist") if handedness == "right" else ("RShoulder", "RWrist")


def arm_elevation_series(
    seq: LandmarkSequence, shoulder: str, wrist: str, reference: AnalysisReference | None = None
) -> np.ndarray:
    """Per-frame angle (degrees) of the shoulder->wrist vector from
    horizontal: 0 = parallel to the ground, +90 = straight up, -90 = straight
    down."""
    reference = reference if reference is not None else infer_reference(seq)
    if reference.up is None:
        return np.full(seq.n_frames, np.nan)
    vec = seq.marker(wrist) - seq.marker(shoulder)
    vertical = vec @ reference.up
    horizontal = np.linalg.norm(vec - vertical[:, None] * reference.up, axis=1)
    return np.degrees(np.arctan2(vertical, horizontal))


def _closest_to_zero(series: np.ndarray, start: int, end: int) -> int:
    lo, hi = min(start, end), max(start, end)
    segment = series[lo : hi + 1]
    finite = np.flatnonzero(np.isfinite(segment))
    return lo + int(finite[np.argmin(np.abs(segment[finite]))]) if finite.size else lo


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
        if not np.isfinite(segment[i - 1 : i + 1]).all():
            continue
        if signs[i] == 0:
            return lo + i, True
        if signs[i - 1] != 0 and signs[i - 1] != signs[i]:
            a, b = lo + i - 1, lo + i
            return (a if abs(series[a]) < abs(series[b]) else b), True
    return _closest_to_zero(series, lo, hi), False


def _phase_progress_estimate(series: np.ndarray, start: int, end: int) -> tuple[int, bool]:
    """Choose the frame nearest halfway between a proxy's phase endpoint values."""
    lo, hi = min(start, end), max(start, end)
    if hi <= lo:
        return lo, False
    segment = series[lo : hi + 1]
    finite = np.flatnonzero(np.isfinite(segment))
    if finite.size < 2:
        return _closest_to_zero(series, lo, hi), False
    start_value, end_value = segment[finite[0]], segment[finite[-1]]
    if abs(end_value - start_value) < 1e-3:
        return _closest_to_zero(series, lo, hi), False
    midpoint = (start_value + end_value) / 2
    offset = int(finite[np.argmin(np.abs(segment[finite] - midpoint))])
    return lo + offset, True


def _proxy_checkpoint(series: np.ndarray, start: int, end: int) -> tuple[int, bool, bool]:
    frame, detected = _find_crossing(series, start, end)
    if detected:
        return frame, True, True
    frame, has_progress = _phase_progress_estimate(series, start, end)
    return frame, False, has_progress


def detect_p_positions(
    seq: LandmarkSequence,
    phases: SwingPhases,
    handedness: Handedness = "right",
    reference: AnalysisReference | None = None,
) -> list[PPosition]:
    reference = reference if reference is not None else infer_reference(seq, handedness)
    if reference.up is None:
        raise ValueError("checkpoint vertical reference is unavailable")
    shoulder, wrist = lead_markers(handedness)

    hand_height = hands_midpoint(seq) @ reference.up
    hip_height_ref = float(seq.marker("Hip")[phases.address_frame] @ reference.up)
    elevation = arm_elevation_series(seq, shoulder, wrist, reference)

    p1 = phases.address_frame
    p4 = phases.top_frame
    p7 = phases.impact_frame

    hand_height_delta = hand_height - hip_height_ref
    p3, p3_detected, p3_available = _proxy_checkpoint(elevation, p1, p4)
    p2, p2_detected, p2_available = _proxy_checkpoint(hand_height_delta, p1, p3)

    p5, p5_detected, p5_available = _proxy_checkpoint(elevation, p4, p7)
    p6, p6_detected, p6_available = _proxy_checkpoint(hand_height_delta, p5, p7)

    # P10 (finish): peak hand height after impact, mirroring "top" on the
    # follow-through side; search the whole post-impact tail since P9 isn't
    # known yet at this point.
    if p7 >= seq.n_frames - 1 or not np.isfinite(hand_height[p7:]).any():
        p10 = p7
    else:
        p10 = p7 + int(np.nanargmax(hand_height[p7:]))

    p9, p9_detected, p9_available = _proxy_checkpoint(elevation, p7, p10)
    p8, p8_detected, p8_available = _proxy_checkpoint(hand_height_delta, p7, p9)

    frames = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10]
    available = [
        True,
        p2_available,
        p3_available,
        True,
        p5_available,
        p6_available,
        True,
        p8_available,
        p9_available,
        p7 < seq.n_frames - 1,
    ]
    detected = [
        True,
        p2_detected,
        p3_detected,
        True,
        p5_detected,
        p6_detected,
        True,
        p8_detected,
        p9_detected,
        p7 < seq.n_frames - 1,
    ]
    estimate_reason = "proxy target not crossed; phase-progress estimate used"
    unavailable_reason = "proxy target was not crossed and phase progress was not measurable"
    estimate_reasons = [
        None,
        estimate_reason if p2_available and not p2_detected else None,
        estimate_reason if p3_available and not p3_detected else None,
        None,
        estimate_reason if p5_available and not p5_detected else None,
        estimate_reason if p6_available and not p6_detected else None,
        None,
        estimate_reason if p8_available and not p8_detected else None,
        estimate_reason if p9_available and not p9_detected else None,
        None,
    ]
    unavailable_reasons = [
        None,
        None if p2_available else unavailable_reason,
        None if p3_available else unavailable_reason,
        None,
        None if p5_available else unavailable_reason,
        None if p6_available else unavailable_reason,
        None,
        None if p8_available else unavailable_reason,
        None if p9_available else unavailable_reason,
        None if p7 < seq.n_frames - 1 else "finish phase has no post-impact frames",
    ]
    # Reserve phase anchors so proxy estimates cannot move P4 or P7. Keep
    # useful estimates selectable when strict ordering adjusts their frames.
    last = seq.n_frames - 1
    for start_index, end_index in ((0, 3), (3, 6), (6, 9)):
        start_frame, end_frame = frames[start_index], min(frames[end_index], last)
        required_gap = end_index - start_index
        if end_frame - start_frame < required_gap:
            for index in range(start_index + 1, end_index):
                frames[index] = min(start_frame + index - start_index, last)
                available[index] = False
                detected[index] = False
                unavailable_reasons[index] = "phase interval is too short for distinct checkpoints"
            if end_index == 9:
                available[end_index] = False
                detected[end_index] = False
                unavailable_reasons[end_index] = (
                    "finish phase is too short for a distinct checkpoint"
                )
            continue

        previous = start_frame
        for index in range(start_index + 1, end_index):
            original = frames[index]
            latest = end_frame - (end_index - index)
            frames[index] = min(max(original, previous + 1), latest)
            if frames[index] != original:
                detected[index] = False
                estimate_reasons[index] = "checkpoint order estimate"
            previous = frames[index]

    if frames[9] <= frames[8]:
        available[9] = False
        detected[9] = False
        unavailable_reasons[9] = "finish phase is too short for a distinct checkpoint"
        frames[9] = min(frames[8] + 1, last)

    return [
        PPosition(
            name=name,
            label=label,
            frame_index=frame,
            time_s=float(seq.times[frame]),
            available=is_available,
            detected=is_detected,
            estimate_reason=estimate_reason,
            unavailable_reason=unavailable_reason,
        )
        for (
            name,
            label,
        ), frame, is_available, is_detected, estimate_reason, unavailable_reason in zip(
            _POSITIONS,
            frames,
            available,
            detected,
            estimate_reasons,
            unavailable_reasons,
            strict=True,
        )
    ]
