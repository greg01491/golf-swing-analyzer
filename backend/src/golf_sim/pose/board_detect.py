"""Checkerboard detection in captured clips (calibration wizard feedback +
intrinsic calibration input)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def find_board_corners(
    clip: Path, corners_nb: tuple[int, int], max_samples: int = 24
) -> list[tuple[np.ndarray, tuple[int, int]]]:
    """Sample frames from a clip and return (refined corner points, image size)
    for each frame where the full board is found."""
    pattern = tuple(corners_nb)
    cap = cv2.VideoCapture(str(clip))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    found = []
    try:
        for i in range(min(max_samples, total)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * total / min(max_samples, total)))
            ok, frame = cap.read()
            if not ok:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            try:
                ret, corners = cv2.findChessboardCorners(
                    gray, pattern, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
                )
            except cv2.error:
                # OpenCV's adaptive-threshold step can throw on degenerate
                # frames (e.g. too small/corrupt) -- treat as "not found"
                # rather than crash the whole wizard capture.
                continue
            if not ret:
                continue
            corners = cv2.cornerSubPix(
                gray,
                corners,
                (11, 11),
                (-1, -1),
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
            )
            found.append((corners, (gray.shape[1], gray.shape[0])))
    finally:
        cap.release()
    return found


def count_board_in_clip(clip: Path, corners_nb: tuple[int, int], samples: int = 6) -> int:
    """Cheap wizard feedback: in how many of `samples` frames is the board
    fully visible/detectable?"""
    return len(find_board_corners(clip, corners_nb, max_samples=samples))
