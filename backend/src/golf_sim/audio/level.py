"""Pure signal-level math: RMS and dBFS from a block of audio samples."""

from __future__ import annotations

import numpy as np

# Floor to avoid log10(0) for digital silence.
_MIN_RMS = 1e-10


def compute_rms(block: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))


def rms_to_db(rms: float) -> float:
    """dBFS relative to a full-scale sine (1.0 amplitude)."""
    return 20.0 * np.log10(max(rms, _MIN_RMS))


def compute_level_db(block: np.ndarray) -> float:
    return rms_to_db(compute_rms(block))
