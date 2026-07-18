"""Failure-recovery behavior (NFR5): device loss and corrupt data must not
kill threads or take down the API."""

import json
import time

from golf_sim.api.sessions import list_sessions
from golf_sim.audio.service import AudioTriggerService
from golf_sim.audio.trigger import TriggerDetector
from golf_sim.capture.buffer import RollingBuffer
from golf_sim.capture.stream import CameraStream


class FailingCameraSource:
    fps = 30.0

    def open(self):
        pass

    def read(self):
        raise RuntimeError("USB device unplugged")

    def close(self):
        pass


class FailingAudioSource:
    def open(self):
        pass

    def read(self):
        raise RuntimeError("mic driver gone")

    def close(self):
        pass


def test_camera_stream_survives_raising_source_and_reports_unhealthy():
    stream = CameraStream("camera_1", FailingCameraSource(), RollingBuffer(max_age_s=1.0))
    stream.start()
    try:
        deadline = time.monotonic() + 5.0
        while stream.healthy and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not stream.healthy
        assert stream.last_error == "USB device unplugged"
        assert stream._thread is not None and stream._thread.is_alive()
    finally:
        stream.stop()


def test_audio_service_survives_raising_source():
    detector = TriggerDetector(threshold_db=-20.0, cooldown_s=1.0)
    service = AudioTriggerService(FailingAudioSource(), detector, on_trigger=lambda t: None)
    service.start()
    try:
        deadline = time.monotonic() + 3.0
        while service.last_error is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert service.last_error == "mic driver gone"
        assert service.last_level_db is None
        assert service._thread is not None and service._thread.is_alive()
    finally:
        service.stop()


def test_corrupt_session_metadata_does_not_break_listing(tmp_path):
    root = tmp_path / "sessions"
    good = root / "20260101T000000Z-good0001"
    good.mkdir(parents=True)
    (good / "metadata.json").write_text(json.dumps({"created_at": "2026-01-01T00:00:00+00:00"}))
    corrupt = root / "20260102T000000Z-bad00001"
    corrupt.mkdir()
    (corrupt / "metadata.json").write_text("{not valid json")

    listing = list_sessions(tmp_path)

    assert [s["id"] for s in listing] == [
        "20260102T000000Z-bad00001",
        "20260101T000000Z-good0001",
    ]
    assert listing[0]["created_at"] is None
    assert listing[1]["created_at"] == "2026-01-01T00:00:00+00:00"
