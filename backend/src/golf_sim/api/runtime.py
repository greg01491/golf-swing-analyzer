"""Holds the live capture + audio-trigger services behind the API.

Kept separate from the FastAPI app so the app stays testable without
touching real cameras/mics: tests construct a CaptureRuntime with synthetic
sources, the real server constructs one from config.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from golf_sim.audio.service import AudioTriggerService
from golf_sim.audio.source import AudioSource, SounddeviceMicSource
from golf_sim.audio.trigger import TriggerDetector
from golf_sim.capture.service import CaptureService
from golf_sim.capture.source import CameraSource
from golf_sim.config import Config

logger = logging.getLogger(__name__)


class CaptureRuntime:
    def __init__(
        self,
        config: Config,
        camera_sources: dict[str, CameraSource] | None = None,
        audio_source: AudioSource | None = None,
    ):
        self.config = config
        self._camera_sources = camera_sources
        self._audio_source = audio_source
        self._capture: CaptureService | None = None
        self._audio: AudioTriggerService | None = None
        self._lock = threading.Lock()
        self.last_session_dir: Path | None = None
        self.last_error: str | None = None
        # Called with the session dir after every successful capture; the API
        # server wires this to auto-processing when processing.auto_process
        # is enabled. Must not raise.
        self.on_session: Callable[[Path], None] | None = None

    @property
    def running(self) -> bool:
        return self._capture is not None

    @property
    def armed(self) -> bool:
        return self._audio is not None and self._audio.is_armed()

    @property
    def mic_level_db(self) -> float | None:
        return self._audio.last_level_db if self._audio else None

    @property
    def mic_error(self) -> str | None:
        return self._audio.last_error if self._audio else None

    @property
    def camera_health(self) -> dict[str, bool]:
        if self._capture is None:
            return {}
        return {role: stream.healthy for role, stream in self._capture.streams.items()}

    def latest_frame(self, role: str):
        """Most recent buffered frame image for a camera (None if not
        running/empty) -- powers the live preview endpoint."""
        if self._capture is None or role not in self._capture.streams:
            return None
        frame = self._capture.streams[role].buffer.latest()
        return None if frame is None else frame.image

    def capture_calibration_shot(self) -> Path:
        """Immediate capture for the calibration wizard: same pipeline as a
        trigger but never dispatches auto-processing (the caller marks the
        session as a calibration shot instead)."""
        if not self.running:
            self.start()
        assert self._capture is not None
        import time as _time

        return self._capture.capture_now(_time.monotonic())

    def _on_trigger(self, trigger_time: float) -> None:
        assert self._capture is not None
        try:
            self.last_session_dir = self._capture.capture_now(trigger_time)
            logger.info("captured session %s", self.last_session_dir)
        except Exception as exc:  # capture failure must not kill the listener (NFR5)
            self.last_error = str(exc)
            logger.exception("capture failed")
            return
        if self.on_session is not None:
            try:
                self.on_session(self.last_session_dir)
            except Exception:  # processing kickoff failure must not kill the listener
                logger.exception("on_session hook failed")

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            self.last_error = None
            capture = CaptureService(self.config, sources=self._camera_sources)
            capture.start()
            audio_source = self._audio_source or SounddeviceMicSource(
                device=self.config.audio_trigger.device
            )
            detector = TriggerDetector(
                threshold_db=self.config.audio_trigger.threshold_db,
                cooldown_s=self.config.audio_trigger.trigger_cooldown_s,
            )
            audio = AudioTriggerService(audio_source, detector, self._on_trigger)
            audio.start()
            self._capture, self._audio = capture, audio

    def stop(self) -> None:
        with self._lock:
            if self._audio is not None:
                self._audio.stop()
                self._audio = None
            if self._capture is not None:
                self._capture.stop()
                self._capture = None

    def arm(self) -> None:
        if not self.running:
            self.start()
        assert self._audio is not None
        self._audio.arm()

    def disarm(self) -> None:
        if self._audio is not None:
            self._audio.disarm()

    def manual_trigger(self) -> None:
        if not self.running:
            self.start()
        assert self._audio is not None
        self._audio.manual_trigger()
