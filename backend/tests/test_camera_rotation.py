"""Camera rotation correction: a physically sideways/upside-down mounted
camera must be corrected at the source (every frame, before it reaches the
buffer/saved clips/pose estimation), not just cosmetically in a preview --
a rotated person confuses a pose model trained on upright people."""

import cv2
import numpy as np
import pytest

from golf_sim.capture.source import OpenCVCameraSource


class _FakeCap:
    def __init__(self, image):
        self._image = image

    def read(self):
        return True, self._image.copy()


def _asymmetric_frame():
    # 4x2 (h x w) frame with a distinct marker in one corner, so rotation
    # direction is unambiguous (a symmetric test image couldn't tell
    # clockwise from counter-clockwise apart)
    frame = np.zeros((4, 2, 3), dtype=np.uint8)
    frame[0, 0] = [255, 0, 0]  # top-left marker
    return frame


@pytest.mark.parametrize(
    "rotation_deg,cv2_flag",
    [
        (90, cv2.ROTATE_90_CLOCKWISE),
        (180, cv2.ROTATE_180),
        (270, cv2.ROTATE_90_COUNTERCLOCKWISE),
    ],
)
def test_read_applies_configured_rotation(rotation_deg, cv2_flag):
    frame = _asymmetric_frame()
    source = OpenCVCameraSource(0, 1280, 720, 60, rotation_deg=rotation_deg)
    source._cap = _FakeCap(frame)

    result = source.read()

    expected = cv2.rotate(frame, cv2_flag)
    assert np.array_equal(result.image, expected)
    # 90/270 rotate a 4x2 frame into 2x4
    assert result.image.shape[:2] == expected.shape[:2]


def test_read_applies_no_rotation_by_default():
    frame = _asymmetric_frame()
    source = OpenCVCameraSource(0, 1280, 720, 60)
    source._cap = _FakeCap(frame)

    result = source.read()

    assert np.array_equal(result.image, frame)


def test_invalid_rotation_rejected():
    with pytest.raises(ValueError, match="rotation_deg"):
        OpenCVCameraSource(0, 1280, 720, 60, rotation_deg=45)
