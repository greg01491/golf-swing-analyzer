import time

import numpy as np
import pytest

from golf_sim.capture.buffer import RollingBuffer
from golf_sim.capture.extract import ExtractTimeoutError, extract_window
from golf_sim.capture.frame import Frame
from golf_sim.capture.service import CaptureService
from golf_sim.capture.source import SyntheticCameraSource
from golf_sim.config import (
    ApiConfig,
    AudioTriggerConfig,
    CalibrationConfig,
    CameraDeviceConfig,
    CamerasConfig,
    Config,
    MetricsConfig,
    PoseConfig,
    ProcessingConfig,
    StorageConfig,
)


def _tiny_frame() -> np.ndarray:
    return np.zeros((2, 2, 3), dtype=np.uint8)


def test_rolling_buffer_evicts_frames_older_than_max_age():
    buffer = RollingBuffer(max_age_s=1.0)
    base = time.monotonic()
    buffer.push(Frame(timestamp=base, image=_tiny_frame()))
    buffer.push(Frame(timestamp=base + 0.5, image=_tiny_frame()))
    buffer.push(Frame(timestamp=base + 2.0, image=_tiny_frame()))  # evicts the first two

    snapshot = buffer.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0].timestamp == pytest.approx(base + 2.0)


def test_extract_window_filters_to_trigger_relative_range():
    buffer = RollingBuffer(max_age_s=10.0)
    base = time.monotonic()
    for i in range(10):
        buffer.push(Frame(timestamp=base + i * 0.1, image=_tiny_frame()))

    # Window edges (base+0.25, base+0.65) deliberately fall *between* frame
    # samples (spaced 0.1 apart), not exactly on one -- landing exactly on a
    # sample's timestamp makes the test's pass/fail depend on float rounding
    # (observed flaky on CI, where time.monotonic()'s larger absolute value
    # made epsilon-level rounding more likely to tip a boundary frame in/out).
    trigger_time = base + 0.6
    frames = extract_window(
        buffer, trigger_time, pre_capture_delay_s=0.35, capture_duration_s=0.4, timeout_s=1.0
    )

    # window is [base+0.25, base+0.65] -> indices 3..6 inclusive (4 frames)
    assert len(frames) == 4
    assert frames[0].timestamp == pytest.approx(base + 0.3)
    assert frames[-1].timestamp == pytest.approx(base + 0.6)


def test_extract_window_times_out_if_buffer_never_fills():
    buffer = RollingBuffer(max_age_s=10.0)
    with pytest.raises(ExtractTimeoutError):
        extract_window(
            buffer,
            trigger_time=time.monotonic() + 100,
            pre_capture_delay_s=0.1,
            capture_duration_s=0.1,
            poll_interval_s=0.01,
            timeout_s=0.05,
        )


def _tiny_config(tmp_path) -> Config:
    return Config(
        audio_trigger=AudioTriggerConfig(
            device=None,
            threshold_db=-20.0,
            pre_capture_delay_s=0.15,
            capture_duration_s=0.3,
            trigger_cooldown_s=1.0,
        ),
        cameras=CamerasConfig(
            buffer_margin_s=0.15,
            devices=[
                CameraDeviceConfig(id=0, role="camera_1", width=8, height=6, fps=30),
                CameraDeviceConfig(id=1, role="camera_2", width=8, height=6, fps=30),
            ],
        ),
        pose=PoseConfig(pose_model="Body_with_feet", mode="balanced", save_debug_video=True),
        calibration=CalibrationConfig(
            dir=str(tmp_path / "calibration"),
            max_age_days=60,
            checkerboard_corners=[4, 7],
            checkerboard_square_size_mm=60,
        ),
        metrics=MetricsConfig(reference_ranges={}),
        processing=ProcessingConfig(auto_process=False),
        storage=StorageConfig(data_dir=str(tmp_path), db_file=str(tmp_path / "sessions.db")),
        api=ApiConfig(host="127.0.0.1", port=8765),
    )


def test_manual_capture_produces_two_synced_clips(tmp_path):
    config = _tiny_config(tmp_path)
    sources = {
        dev.role: SyntheticCameraSource(fps=dev.fps, width=dev.width, height=dev.height)
        for dev in config.cameras.devices
    }
    service = CaptureService(config, sources=sources)
    service.start()
    try:
        time.sleep(config.audio_trigger.pre_capture_delay_s + config.cameras.buffer_margin_s)
        session_dir = service.capture_now()
    finally:
        service.stop()

    assert (session_dir / "camera_1.mp4").exists()
    assert (session_dir / "camera_2.mp4").exists()
    assert (session_dir / "metadata.json").exists()

    import json

    metadata = json.loads((session_dir / "metadata.json").read_text())
    cam1_frames = metadata["cameras"]["camera_1"]["frame_count"]
    cam2_frames = metadata["cameras"]["camera_2"]["frame_count"]
    expected = config.audio_trigger.capture_duration_s * 30
    assert cam1_frames == cam2_frames  # both cameras produced the same window length
    assert expected * 0.7 <= cam1_frames <= expected * 1.3


def test_capture_now_accepts_explicit_trigger_time(tmp_path):
    # the audio trigger service passes the exact moment it detected the
    # impact, rather than letting capture_now() stamp its own "now"
    config = _tiny_config(tmp_path)
    sources = {
        dev.role: SyntheticCameraSource(fps=dev.fps, width=dev.width, height=dev.height)
        for dev in config.cameras.devices
    }
    service = CaptureService(config, sources=sources)
    service.start()
    try:
        time.sleep(config.audio_trigger.pre_capture_delay_s + config.cameras.buffer_margin_s)
        explicit_trigger_time = time.monotonic() - 0.05
        session_dir = service.capture_now(trigger_time=explicit_trigger_time)
    finally:
        service.stop()

    assert (session_dir / "camera_1.mp4").exists()
