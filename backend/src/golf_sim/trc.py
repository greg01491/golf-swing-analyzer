"""Shared reader for Pose2Sim .trc 3D landmark files -- the data contract
between the pose pipeline (which writes them) and the analysis engine and
viewer (which consume them)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class LandmarkSequence:
    marker_names: list[str]
    times: np.ndarray  # [n_frames]
    coords: np.ndarray  # [n_frames, n_markers, 3]

    @property
    def n_frames(self) -> int:
        return len(self.times)

    @property
    def fps(self) -> float:
        if len(self.times) < 2:
            return 0.0
        return 1.0 / float(np.mean(np.diff(self.times)))

    def marker(self, name: str) -> np.ndarray:
        """[n_frames, 3] trajectory for one marker."""
        return self.coords[:, self.marker_names.index(name), :]

    def has_marker(self, name: str) -> bool:
        return name in self.marker_names


def read_trc(path: Path) -> LandmarkSequence:
    lines = Path(path).read_text().splitlines()
    # line 3 (0-indexed): tab-separated marker names starting at column 2
    marker_names = [name for name in lines[3].split("\t")[2:] if name.strip()]
    rows = []
    for line in lines[5:]:
        if not line.strip():
            continue
        rows.append([float(v) if v.strip() else np.nan for v in line.split("\t")])
    data = np.array(rows)
    times = data[:, 1]
    coords = data[:, 2 : 2 + 3 * len(marker_names)].reshape(len(data), len(marker_names), 3)
    return LandmarkSequence(marker_names=marker_names, times=times, coords=coords)
