"""Camera sources: a real OpenCV-backed USB camera, and a synthetic
generator so the rest of the capture pipeline is testable without hardware."""

from __future__ import annotations

import time
from typing import Protocol

import cv2
import numpy as np

from golf_sim.capture.frame import Frame


class CameraSource(Protocol):
    fps: float

    def open(self) -> None: ...
    def read(self) -> Frame | None: ...
    def close(self) -> None: ...


class OpenCVCameraSource:
    def __init__(self, index: int, width: int, height: int, fps: float):
        self.index = index
        self.width = width
        self.height = height
        self.fps = fps
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            raise RuntimeError(f"could not open camera index {self.index}")
        self._cap = cap

    def read(self) -> Frame | None:
        assert self._cap is not None, "call open() first"
        ok, image = self._cap.read()
        if not ok:
            return None
        return Frame(timestamp=time.monotonic(), image=image)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class SyntheticCameraSource:
    """Generates paced synthetic frames for tests/dev without real cameras."""

    def __init__(self, fps: float = 30.0, width: int = 64, height: int = 48):
        self.fps = fps
        self.width = width
        self.height = height
        self._frame_period = 1.0 / fps
        self._next_due: float | None = None
        self._count = 0

    def open(self) -> None:
        self._next_due = time.monotonic()
        self._count = 0

    def read(self) -> Frame | None:
        assert self._next_due is not None, "call open() first"
        now = time.monotonic()
        if now < self._next_due:
            time.sleep(self._next_due - now)
        image = np.full((self.height, self.width, 3), self._count % 256, dtype=np.uint8)
        self._count += 1
        self._next_due += self._frame_period
        return Frame(timestamp=time.monotonic(), image=image)

    def close(self) -> None:
        self._next_due = None
