"""Listens to a mic source, detects trigger events, and dispatches them --
decoupled from the capture pipeline via a plain callback so this module
knows nothing about cameras/storage (see CONTRIBUTING.md module boundaries)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from golf_sim.audio.level import compute_level_db
from golf_sim.audio.source import AudioSource
from golf_sim.audio.trigger import TriggerDetector


class AudioTriggerService:
    def __init__(
        self,
        source: AudioSource,
        detector: TriggerDetector,
        on_trigger: Callable[[float], None],
    ):
        self.source = source
        self.detector = detector
        self.on_trigger = on_trigger
        self.last_level_db: float | None = None
        self.last_error: str | None = None

        self._armed = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._dispatch_threads: list[threading.Thread] = []

    def start(self) -> None:
        self.source.open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audio-trigger", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                block = self.source.read()
            except Exception as exc:
                # Mic unplugged/driver error must not kill the listener
                # thread (NFR5): surface the error, blank the level meter,
                # and keep retrying at a gentle pace in case it comes back.
                self.last_error = str(exc)
                self.last_level_db = None
                time.sleep(1.0)
                continue
            if block is None:
                time.sleep(0.001)
                continue
            self.last_error = None
            level_db = compute_level_db(block.samples)
            self.last_level_db = level_db
            if self._armed.is_set() and self.detector.check(level_db, block.timestamp):
                self._dispatch(block.timestamp)

    def _dispatch(self, trigger_time: float) -> None:
        thread = threading.Thread(target=self.on_trigger, args=(trigger_time,), daemon=True)
        thread.start()
        self._dispatch_threads.append(thread)

    def arm(self) -> None:
        self._armed.set()

    def disarm(self) -> None:
        self._armed.clear()

    def is_armed(self) -> bool:
        return self._armed.is_set()

    def manual_trigger(self) -> None:
        """Fallback for when auto-detection misses (FR8) -- bypasses the
        threshold/cooldown check but still starts a cooldown window so it
        doesn't immediately double-fire with a real detection."""
        now = time.monotonic()
        self.detector.reset_cooldown(now)
        self._dispatch(now)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.source.close()
        for thread in self._dispatch_threads:
            thread.join(timeout=10.0)
        self._dispatch_threads.clear()
