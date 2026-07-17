from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class Frame:
    """A single captured frame, timestamped on the host's monotonic clock so
    that two independently-read camera streams share one clock domain
    (plan.md Spike B)."""

    timestamp: float
    image: np.ndarray
