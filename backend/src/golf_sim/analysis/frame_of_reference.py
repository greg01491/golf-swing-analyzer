"""Body-anchored reference frame for metric computations.

The TRC's world axes depend on how the rig was calibrated, so nothing here
assumes which axis is up or where the target line is. Instead:

- vertical: the world axis with the largest ankle-to-head separation
  (a standing golfer is much taller than they are wide from any calibrated
  camera pair), signed so "up" is positive.
- turn angles: measured as rotation of a body line (shoulders/hips)
  projected onto the horizontal plane, relative to that line's orientation
  at address -- so no target-line knowledge is needed.
"""

from __future__ import annotations

import numpy as np

from golf_sim.trc import LandmarkSequence


def vertical_axis(seq: LandmarkSequence) -> tuple[int, float]:
    """Returns (axis_index, sign) such that coords[..., axis] * sign is height."""
    head_name = next(n for n in ("Head", "Neck", "Nose") if seq.has_marker(n))
    head = np.nanmedian(seq.marker(head_name), axis=0)
    ankles = np.nanmedian((seq.marker("RAnkle") + seq.marker("LAnkle")) / 2, axis=0)
    diff = head - ankles
    axis = int(np.nanargmax(np.abs(diff)))
    return axis, float(np.sign(diff[axis]))


def horizontal_angle_series(
    seq: LandmarkSequence, left_marker: str, right_marker: str, reference_frame: int
) -> np.ndarray:
    """Per-frame signed rotation (degrees) of the left->right body line in the
    horizontal plane, relative to its orientation at reference_frame."""
    up_axis, _ = vertical_axis(seq)
    horizontal_axes = [i for i in range(3) if i != up_axis]

    line = seq.marker(right_marker) - seq.marker(left_marker)
    u = line[:, horizontal_axes[0]]
    v = line[:, horizontal_axes[1]]
    angles = np.degrees(np.arctan2(v, u))
    relative = angles - angles[reference_frame]
    # wrap to [-180, 180] so a turn through the axis seam doesn't jump
    return (relative + 180) % 360 - 180
