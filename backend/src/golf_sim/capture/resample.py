"""Resample a captured frame window onto an exact fps grid.

Real webcam drivers don't deliver clean frame paces -- bring-up found one
camera returning reads at ~2x its real frame rate (duplicated frames) while
the other paced correctly at 60fps. Saving raw read sequences would give the
two cameras different frame counts for the same time window, and Pose2Sim's
triangulation pairs cameras *by frame index* -- so the pairing would drift.

Snapping every clip to the same timestamp grid (nearest frame per grid
instant) makes both cameras' clips identical in length and time-aligned by
construction, and also absorbs occasional dropped frames.
"""

from __future__ import annotations

import numpy as np

from golf_sim.capture.frame import Frame


def resample_to_grid(
    frames: list[Frame], start_time: float, duration_s: float, fps: float
) -> list[Frame]:
    if not frames:
        raise ValueError("cannot resample an empty frame list")
    grid = start_time + np.arange(round(duration_s * fps)) / fps
    stamps = np.array([f.timestamp for f in frames])
    nearest = np.searchsorted(stamps, grid)
    out: list[Frame] = []
    for target, right in zip(grid, nearest, strict=True):
        right = min(right, len(frames) - 1)
        left = max(right - 1, 0)
        best = left if abs(stamps[left] - target) <= abs(stamps[right] - target) else right
        out.append(Frame(timestamp=float(grid[len(out)]), image=frames[best].image))
    return out
