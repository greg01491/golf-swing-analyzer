"""Background thread that continuously reads a camera source into a rolling
buffer, independent of when/whether a capture is ever triggered."""

from __future__ import annotations

import threading

from golf_sim.capture.buffer import RollingBuffer
from golf_sim.capture.source import CameraSource


class CameraStream:
    def __init__(self, role: str, source: CameraSource, buffer: RollingBuffer):
        self.role = role
        self.source = source
        self.buffer = buffer
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.source.open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"camera-{self.role}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            frame = self.source.read()
            if frame is not None:
                self.buffer.push(frame)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.source.close()
