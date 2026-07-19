"""Orchestrates the per-camera streams and turns a trigger into a saved
session -- the module the audio-trigger service (Phase 2) will call into."""

from __future__ import annotations

import time
from pathlib import Path

from golf_sim.capture.buffer import RollingBuffer
from golf_sim.capture.extract import extract_window
from golf_sim.capture.resample import resample_to_grid
from golf_sim.capture.source import CameraSource, OpenCVCameraSource
from golf_sim.capture.stream import CameraStream
from golf_sim.capture.writer import SessionWriter
from golf_sim.config import REPO_ROOT, Config


class CaptureService:
    def __init__(self, config: Config, sources: dict[str, CameraSource] | None = None):
        self.config = config
        # Must cover the *whole* capture window, not just the pre-trigger delay:
        # extraction keeps polling this same buffer for post-trigger frames too,
        # and eviction is age-relative-to-newest-frame, so anything shorter would
        # evict the start of the window before extraction finishes.
        buffer_age = config.audio_trigger.capture_duration_s + config.cameras.buffer_margin_s

        self.streams: dict[str, CameraStream] = {}
        self.camera_meta: dict[str, dict] = {}
        for dev in config.cameras.devices:
            source = (
                sources[dev.role]
                if sources is not None
                else OpenCVCameraSource(
                    dev.id,
                    dev.width,
                    dev.height,
                    dev.fps,
                    name=dev.name,
                    rotation_deg=dev.rotation_deg,
                )
            )
            buffer = RollingBuffer(max_age_s=buffer_age)
            self.streams[dev.role] = CameraStream(dev.role, source, buffer)
            # a 90/270 rotation swaps the saved frame's actual dimensions --
            # reflect that here so metadata.json matches the real clip
            rotated_90 = dev.rotation_deg in (90, 270)
            self.camera_meta[dev.role] = {
                "camera_id": dev.id,
                "width": dev.height if rotated_90 else dev.width,
                "height": dev.width if rotated_90 else dev.height,
                "fps": dev.fps,
            }

        self.writer = SessionWriter(REPO_ROOT / config.storage.data_dir)

    def start(self) -> None:
        for stream in self.streams.values():
            stream.start()

    def stop(self) -> None:
        for stream in self.streams.values():
            stream.stop()

    def capture_now(self, trigger_time: float | None = None) -> Path:
        """trigger_time defaults to now (manual/dev capture); the audio
        trigger service passes the exact moment it detected the impact so
        the extracted window is anchored to that instant, not to whenever
        this method happens to run."""
        if trigger_time is None:
            trigger_time = time.monotonic()
        pre = self.config.audio_trigger.pre_capture_delay_s
        duration = self.config.audio_trigger.capture_duration_s

        # Snap every camera's window onto the same exact fps grid: real
        # drivers duplicate/drop frames unpredictably (one rig camera read at
        # ~2x its true rate), and downstream triangulation pairs cameras by
        # frame index -- so identical, time-aligned frame counts are required.
        start_time = trigger_time - pre
        clips = {}
        for role, stream in self.streams.items():
            raw = extract_window(stream.buffer, trigger_time, pre, duration)
            clips[role] = resample_to_grid(
                raw, start_time, duration, fps=self.camera_meta[role]["fps"]
            )
        return self.writer.write_session(clips, self.camera_meta, pre, duration)
