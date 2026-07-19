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


def resolve_camera_index(name: str, device_names: list[str] | None = None) -> int:
    """DirectShow camera indices are NOT stable across processes on Windows
    (observed live: the same physical camera at index 0 in one process and
    the laptop webcam there in the next -- a swing recorded from the wrong
    camera). Device *names* are stable, so config can pin a name and we
    resolve it to whatever index it holds right now."""
    if device_names is None:
        from pygrabber.dshow_graph import FilterGraph

        device_names = FilterGraph().get_input_devices()
    try:
        return device_names.index(name)
    except ValueError:
        raise RuntimeError(f"no camera named {name!r} connected (found: {device_names})") from None


_ROTATE_FLAGS = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


class OpenCVCameraSource:
    def __init__(
        self,
        index: int,
        width: int,
        height: int,
        fps: float,
        name: str | None = None,
        rotation_deg: int = 0,
    ):
        """If name is given it takes precedence over index (see
        resolve_camera_index for why). rotation_deg corrects a physically
        sideways/upside-down mounted camera -- applied to every frame at the
        source, before it reaches the buffer, saved clips, live preview, or
        pose estimation, since a sideways person confuses a pose model
        trained on upright people (not just a cosmetic preview issue)."""
        if rotation_deg not in _ROTATE_FLAGS:
            raise ValueError(
                f"rotation_deg must be one of {sorted(_ROTATE_FLAGS)}, got {rotation_deg}"
            )
        self.index = index
        self.name = name
        self.width = width
        self.height = height
        self.fps = fps
        self.rotation_deg = rotation_deg
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        index = self.index if self.name is None else resolve_camera_index(self.name)
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            raise RuntimeError(f"could not open camera {self.name or index!r}")
        self._cap = cap

    def read(self) -> Frame | None:
        assert self._cap is not None, "call open() first"
        ok, image = self._cap.read()
        if not ok:
            return None
        flag = _ROTATE_FLAGS[self.rotation_deg]
        if flag is not None:
            image = cv2.rotate(image, flag)
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
