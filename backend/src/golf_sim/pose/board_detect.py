"""Checkerboard detection in captured clips (calibration wizard feedback +
intrinsic calibration input)."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _detect_board(gray: np.ndarray, pattern: tuple[int, int]) -> np.ndarray | None:
    """Find the full checkerboard in a grayscale frame, or None.

    Tries the sector-based detector (findChessboardCornersSB) first -- it is
    markedly more robust to blur, uneven lighting, and perspective than the
    classic detector, and self-refines to sub-pixel -- then falls back to the
    classic adaptive-threshold detector + cornerSubPix.
    """
    try:
        ret, corners = cv2.findChessboardCornersSB(
            gray, pattern, cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_EXHAUSTIVE
        )
        if ret:
            return corners
    except (cv2.error, AttributeError):
        pass  # SB unavailable on very old OpenCV, or threw on a degenerate frame
    try:
        ret, corners = cv2.findChessboardCorners(
            gray, pattern, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )
    except cv2.error:
        return None
    if not ret:
        return None
    return cv2.cornerSubPix(
        gray,
        corners,
        (11, 11),
        (-1, -1),
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
    )


def find_board_corners(
    clip: Path, corners_nb: tuple[int, int], max_samples: int = 24
) -> list[tuple[np.ndarray, tuple[int, int]]]:
    """Sample frames from a clip and return (refined corner points, image size)
    for each frame where the full board is found."""
    pattern = tuple(corners_nb)
    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        logger.error(f"Cannot open video file: {clip}")
        return []
    
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total == 0:
        logger.error(f"Video has no frames: {clip}")
        cap.release()
        return []
    
    found = []
    samples_to_check = min(max_samples, total)
    logger.debug(f"Checking {samples_to_check} frames from {clip} for {pattern} checkerboard")
    
    try:
        for i in range(samples_to_check):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * total / samples_to_check))
            ok, frame = cap.read()
            if not ok:
                logger.debug(f"  Frame {i}: read failed")
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners = _detect_board(gray, pattern)
            if corners is not None:
                found.append((corners, (gray.shape[1], gray.shape[0])))
                logger.debug(f"  Frame {i}: board detected ✓")
            else:
                logger.debug(f"  Frame {i}: no board")
    finally:
        cap.release()
    
    logger.info(f"Board detection in {clip}: {len(found)} / {samples_to_check} frames detected")
    return found


def count_board_in_clip(clip: Path, corners_nb: tuple[int, int], samples: int = 6) -> int:
    """Cheap wizard feedback: in how many of `samples` frames is the board
    fully visible/detectable?"""
    try:
        count = len(find_board_corners(clip, corners_nb, max_samples=samples))
        return count
    except Exception as e:
        logger.error(f"Board detection failed for {clip}: {e}", exc_info=True)
        return 0
