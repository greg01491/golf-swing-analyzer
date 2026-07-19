import time

import cv2

from golf_sim.config import CameraDeviceConfig, SystemRequirementsConfig
from golf_sim.diagnostics.camera_check import check_camera


class _FakeCap:
    def __init__(self, width, height, opens=True, read_delay_s=0.0):
        self._width = width
        self._height = height
        self._opens = opens
        self._read_delay_s = read_delay_s
        self.released = False

    def isOpened(self):
        return self._opens

    def get(self, prop_id):
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return self._width
        if prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return self._height
        return 0

    def read(self):
        if self._read_delay_s:
            time.sleep(self._read_delay_s)
        return True, object()

    def release(self):
        self.released = True


def _dev(**overrides) -> CameraDeviceConfig:
    base = dict(id=0, role="camera_1", width=1280, height=720, fps=60)
    base.update(overrides)
    return CameraDeviceConfig(**base)


def _requirements(**overrides) -> SystemRequirementsConfig:
    base = dict(min_camera_width=1280, min_camera_height=720, min_camera_fps=0)
    base.update(overrides)
    return SystemRequirementsConfig(**base)


class _HangingCap:
    """A camera whose read() never returns -- simulates a stalled USB
    driver, found live: cap.read() has no built-in timeout and can block
    forever."""

    def isOpened(self):
        return True

    def get(self, prop_id):
        return 0

    def read(self):
        time.sleep(1_000_000)
        return True, object()

    def release(self):
        pass


def test_passes_when_camera_delivers_requested_spec():
    fake = _FakeCap(1280, 720)
    result = check_camera(_dev(), _requirements(), open_capture=lambda *a: fake, warmup_s=0)
    assert result.opened is True
    assert result.meets_minimum is True
    assert result.warnings == []
    assert fake.released is True


def test_flags_low_resolution():
    fake = _FakeCap(640, 480)
    result = check_camera(_dev(), _requirements(), open_capture=lambda *a: fake, warmup_s=0)
    assert result.meets_minimum is False
    assert any("640x480" in w for w in result.warnings)


def test_flags_low_measured_fps():
    # ~10 fps worth of delay per frame -- deterministically slow regardless
    # of the machine running the test
    fake = _FakeCap(1280, 720, read_delay_s=0.1)
    result = check_camera(
        _dev(), _requirements(min_camera_fps=30), open_capture=lambda *a: fake, warmup_s=0
    )
    assert result.meets_minimum is False
    assert any("fps" in w for w in result.warnings)


def test_reports_error_when_camera_fails_to_open():
    fake = _FakeCap(0, 0, opens=False)
    result = check_camera(_dev(), _requirements(), open_capture=lambda *a: fake, warmup_s=0)
    assert result.opened is False
    assert result.error is not None
    assert fake.released is True


def test_returns_error_instead_of_hanging_when_camera_stalls():
    fake = _HangingCap()
    result = check_camera(
        _dev(),
        _requirements(),
        open_capture=lambda *a: fake,
        probe_timeout_s=0.2,
        warmup_s=0,
    )
    assert result.opened is False
    assert result.error is not None
    assert "did not respond" in result.error
