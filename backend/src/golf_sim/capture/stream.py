"""Background thread that continuously reads a camera source into a rolling
buffer, independent of when/whether a capture is ever triggered."""

from __future__ import annotations

import logging
import threading
import time

from golf_sim.capture.buffer import RollingBuffer
from golf_sim.capture.source import CameraSource

logger = logging.getLogger(__name__)

# After this many consecutive failed reads the stream reports unhealthy
# (a USB camera unplug shows up as read() returning None / raising forever).
_UNHEALTHY_AFTER_FAILURES = 30
_FAILURE_BACKOFF_S = 0.05
# Cheap webcams can stall into delivering all-black frames after long
# continuous streaming (seen live on the rig after ~45min: both cameras
# max-pixel 0 while "healthy"). Reopening the device recovers them.
_REOPEN_AFTER_BLANK_FRAMES = 120


class CameraStream:
    def __init__(self, role: str, source: CameraSource, buffer: RollingBuffer):
        self.role = role
        self.source = source
        self.buffer = buffer
        self.last_error: str | None = None
        self._consecutive_failures = 0
        self._consecutive_blanks = 0
        self.reopen_count = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def healthy(self) -> bool:
        return self._consecutive_failures < _UNHEALTHY_AFTER_FAILURES

    def start(self) -> None:
        self.source.open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"camera-{self.role}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                frame = self.source.read()
            except Exception as exc:  # device yanked mid-read must not kill the thread (NFR5)
                frame = None
                self.last_error = str(exc)
            if frame is not None:
                self.buffer.push(frame)
                self._consecutive_failures = 0
                if frame.image.max() == 0:
                    self._consecutive_blanks += 1
                    if self._consecutive_blanks >= _REOPEN_AFTER_BLANK_FRAMES:
                        self._reopen()
                else:
                    self._consecutive_blanks = 0
                continue
            # back off instead of hot-spinning while the device is gone
            self._consecutive_failures += 1
            if self._consecutive_failures == _UNHEALTHY_AFTER_FAILURES:
                logger.error(
                    "camera %s unhealthy after %d failed reads (%s)",
                    self.role,
                    self._consecutive_failures,
                    self.last_error or "read returned no frame",
                )
            time.sleep(_FAILURE_BACKOFF_S)

    def _reopen(self) -> None:
        logger.warning(
            "camera %s delivered %d consecutive all-black frames -- reopening device",
            self.role,
            self._consecutive_blanks,
        )
        self._consecutive_blanks = 0
        self.reopen_count += 1
        try:
            self.source.close()
            self.source.open()
        except Exception as exc:
            self.last_error = str(exc)
            logger.exception("camera %s reopen failed", self.role)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.source.close()
