"""Coloured golf-ball detection helpers.

The detector is intentionally narrow: it searches only a wrist-anchored ROI in
the down-the-line camera, because the full frame contains too many circular or
bright distractors to be reliable.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _roi_bounds(
    frame_shape: tuple[int, int, int],
    wrist_xy: tuple[float, float],
    roi_offsets: tuple[int, int, int, int],
) -> tuple[int, int, int, int] | None:
    height, width = frame_shape[:2]
    wrist_x, wrist_y = wrist_xy
    x0 = max(0, int(np.floor(wrist_x + roi_offsets[0])))
    x1 = min(width, int(np.ceil(wrist_x + roi_offsets[1])))
    y0 = max(0, int(np.floor(wrist_y + roi_offsets[2])))
    y1 = min(height, int(np.ceil(wrist_y + roi_offsets[3])))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _hue_mask(
    hsv: np.ndarray, hue_range: tuple[int, int], min_saturation: int, min_value: int
) -> np.ndarray:
    lower_hue, upper_hue = hue_range
    lower = np.array([lower_hue, min_saturation, min_value], dtype=np.uint8)
    upper = np.array([upper_hue, 255, 255], dtype=np.uint8)
    if lower_hue <= upper_hue:
        return cv2.inRange(hsv, lower, upper)

    # Hue wrap-around: combine the two halves of the circular hue range.
    first = cv2.inRange(
        hsv,
        np.array([0, min_saturation, min_value], dtype=np.uint8),
        upper,
    )
    second = cv2.inRange(
        hsv,
        lower,
        np.array([179, 255, 255], dtype=np.uint8),
    )
    return cv2.bitwise_or(first, second)


def _mask_for_ball(
    frame: np.ndarray,
    ball_xy: tuple[float, float],
    radius: float,
    hue_range: tuple[int, int],
    min_saturation: int,
    min_value: int,
) -> tuple[np.ndarray, tuple[int, int, int, int]] | None:
    search_radius = max(6, int(np.ceil(radius * 1.6)))
    center_x, center_y = ball_xy
    x0 = max(0, int(np.floor(center_x - search_radius)))
    x1 = min(frame.shape[1], int(np.ceil(center_x + search_radius)))
    y0 = max(0, int(np.floor(center_y - search_radius)))
    y1 = min(frame.shape[0], int(np.ceil(center_y + search_radius)))
    if x1 <= x0 or y1 <= y0:
        return None
    roi = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = _hue_mask(hsv, hue_range, min_saturation, min_value)
    return mask, (x0, y0, x1, y1)


def find_ball_at_address(
    frame: np.ndarray,
    wrist_xy: tuple[float, float],
    hue_range: tuple[int, int],
    *,
    roi_offsets: tuple[int, int, int, int] = (-120, 220, 40, 300),
    min_saturation: int = 70,
    min_value: int = 80,
    min_circularity: float = 0.6,
    min_area_px: float = 40.0,
) -> tuple[float, float, float] | None:
    """Detect a coloured golf ball in a wrist-anchored ROI.

    Returns (center_x, center_y, radius) in full-frame pixel coordinates.
    """
    bounds = _roi_bounds(frame.shape, wrist_xy, roi_offsets)
    if bounds is None:
        return None
    x0, y0, x1, y1 = bounds
    roi = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = _hue_mask(hsv, hue_range, min_saturation, min_value)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best: tuple[float, float, float, float] | None = None
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area_px:
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        if radius <= 0:
            continue
        circularity = area / (np.pi * radius * radius)
        if circularity < min_circularity:
            continue
        score = area * circularity
        if best is None or score > best[0]:
            best = (score, cx, cy, radius)

    if best is None:
        return None
    _, cx, cy, radius = best
    return (cx + x0, cy + y0, radius)


def ball_present(
    frame: np.ndarray,
    ball_xy: tuple[float, float],
    radius: float,
    hue_range: tuple[int, int],
    *,
    min_saturation: int = 70,
    min_value: int = 80,
    present_min_fraction: float = 0.25,
) -> bool:
    """Cheap presence check at a locked ball position."""
    masked = _mask_for_ball(frame, ball_xy, radius, hue_range, min_saturation, min_value)
    if masked is None:
        return False
    mask, _ = masked
    if mask.size == 0:
        return False
    yy, xx = np.ogrid[: mask.shape[0], : mask.shape[1]]
    center_x = (mask.shape[1] - 1) / 2
    center_y = (mask.shape[0] - 1) / 2
    circle = (xx - center_x) ** 2 + (yy - center_y) ** 2 <= (radius * 1.2) ** 2
    coverage = float(np.count_nonzero(mask & circle)) / float(np.count_nonzero(circle) or 1)
    return coverage >= present_min_fraction


def _read_frame_at(clip: Path, frame_index: int) -> np.ndarray | None:
    capture = cv2.VideoCapture(str(clip))
    try:
        if not capture.isOpened():
            return None
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()


def find_ball_address_frame(
    clip: Path,
    ball_xy: tuple[float, float],
    radius: float,
    center_frame: int,
    *,
    hue_range: tuple[int, int],
    min_saturation: int = 70,
    min_value: int = 80,
    present_min_fraction: float = 0.25,
    max_search_frames: int = 20,
) -> int:
    """Walk backward from a known ball location to find the first frame where
    the ball is still visible.
    """
    earliest = center_frame
    start = max(0, center_frame - max_search_frames)
    for frame_index in range(center_frame, start - 1, -1):
        frame = _read_frame_at(clip, frame_index)
        if frame is None:
            break
        if ball_present(
            frame,
            ball_xy,
            radius,
            hue_range,
            min_saturation=min_saturation,
            min_value=min_value,
            present_min_fraction=present_min_fraction,
        ):
            earliest = frame_index
            continue
        break
    return earliest


def detect_impact_by_disappearance(
    clip: Path,
    ball_xy: tuple[float, float],
    start_frame: int,
    fps: float,
    *,
    radius: float,
    hue_range: tuple[int, int],
    min_saturation: int = 70,
    min_value: int = 80,
    present_min_fraction: float = 0.25,
    confirm_frames: int = 2,
    search_seconds: float = 2.0,
) -> int | None:
    """Return the first frame where the ball is absent for long enough to be
    treated as impact.
    """
    capture = cv2.VideoCapture(str(clip))
    try:
        if not capture.isOpened():
            return None
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame + 1)
        last_frame = int(start_frame + max(1, round(search_seconds * fps)))
        miss_streak = 0
        seen_present = False
        frame_index = start_frame + 1
        while frame_index <= last_frame:
            ok, frame = capture.read()
            if not ok:
                break
            present = ball_present(
                frame,
                ball_xy,
                radius,
                hue_range,
                min_saturation=min_saturation,
                min_value=min_value,
                present_min_fraction=present_min_fraction,
            )
            if present:
                seen_present = True
                miss_streak = 0
            elif seen_present:
                miss_streak += 1
                if miss_streak >= confirm_frames:
                    return frame_index - confirm_frames + 1
            frame_index += 1
        return None
    finally:
        capture.release()
