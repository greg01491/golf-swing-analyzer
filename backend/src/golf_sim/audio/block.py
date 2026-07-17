from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class AudioBlock:
    """A block of mono audio samples, timestamped on the same host monotonic
    clock as camera frames (golf_sim.capture.frame.Frame) so a detected
    trigger's time lines up with the video buffers."""

    timestamp: float
    samples: np.ndarray
