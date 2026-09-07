import cv2

from golf_sim.capture.source import apply_camera_controls
from golf_sim.config import CameraDeviceConfig


class _FakeCapture:
    def __init__(self, rejected: set[int] | None = None):
        self.values: dict[int, float] = {}
        self.rejected = rejected or set()

    def set(self, prop_id: int, value: float) -> bool:
        if prop_id in self.rejected:
            return False
        self.values[prop_id] = value
        return True

    def get(self, prop_id: int) -> float:
        return self.values.get(prop_id, -1.0)


def _config(**overrides) -> CameraDeviceConfig:
    return CameraDeviceConfig(id=0, role="camera_1", width=1280, height=720, fps=120, **overrides)


def test_apply_camera_controls_maps_boolean_exposure_and_reads_values():
    capture = _FakeCapture()
    result = apply_camera_controls(
        capture,
        _config(auto_exposure=False, exposure=-8, gain=12, autofocus=False, focus=350),
    )

    assert capture.values[cv2.CAP_PROP_AUTO_EXPOSURE] == 0.25
    assert result["exposure"] == {"requested": -8, "set_ok": True, "readback": -8}
    assert result["autofocus"]["readback"] == 0
    assert result["focus"]["readback"] == 350


def test_apply_camera_controls_reports_rejected_control_without_raising():
    capture = _FakeCapture({cv2.CAP_PROP_GAIN})
    result = apply_camera_controls(capture, _config(gain=20))

    assert result["gain"] == {"requested": 20, "set_ok": False, "readback": -1}
