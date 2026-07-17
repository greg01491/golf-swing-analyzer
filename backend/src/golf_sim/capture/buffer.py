"""Thread-safe rolling buffer of recent frames, bounded by age not count --
sized to (pre-capture delay + margin) per spec.md FR6."""

from __future__ import annotations

import threading
from collections import deque

from golf_sim.capture.frame import Frame


class RollingBuffer:
    def __init__(self, max_age_s: float):
        self.max_age_s = max_age_s
        self._frames: deque[Frame] = deque()
        self._lock = threading.Lock()

    def push(self, frame: Frame) -> None:
        with self._lock:
            self._frames.append(frame)
            cutoff = frame.timestamp - self.max_age_s
            while self._frames and self._frames[0].timestamp < cutoff:
                self._frames.popleft()

    def snapshot(self) -> list[Frame]:
        with self._lock:
            return list(self._frames)

    def latest_timestamp(self) -> float | None:
        with self._lock:
            return self._frames[-1].timestamp if self._frames else None
