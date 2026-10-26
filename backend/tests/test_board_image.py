import cv2
import numpy as np
import pytest

from golf_sim.pose.board_detect import detect_board_corners
from golf_sim.pose.board_image import generate_board_png


@pytest.mark.parametrize("sb_found", [True, False])
def test_board_detector_passes_flags_by_keyword(monkeypatch, sb_found):
    image = np.zeros((64, 64), dtype=np.uint8)
    corners = np.zeros((28, 1, 2), dtype=np.float32)
    calls = []

    def sector_detector(gray, pattern, output_corners=None, flags=0):
        assert output_corners is None
        assert flags == cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_EXHAUSTIVE
        calls.append("sector")
        return sb_found, corners if sb_found else None

    def classic_detector(gray, pattern, output_corners=None, flags=0):
        assert output_corners is None
        assert flags == cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
        calls.append("classic")
        return True, corners

    monkeypatch.setattr(cv2, "findChessboardCornersSB", sector_detector)
    monkeypatch.setattr(cv2, "findChessboardCorners", classic_detector)
    monkeypatch.setattr(cv2, "cornerSubPix", lambda *args: corners)

    assert detect_board_corners(image, (4, 7)) is corners
    assert calls == (["sector"] if sb_found else ["sector", "classic"])


def test_generates_valid_png_with_detectable_checkerboard():
    png_bytes = generate_board_png((4, 7))
    array = cv2.imdecode(np.frombuffer(png_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)

    assert array is not None
    # A4 at 300 DPI
    assert array.shape == (3508, 2480)

    found, _ = cv2.findChessboardCorners(array, (4, 7))
    assert found


def test_rejects_a_board_too_large_for_a4():
    with pytest.raises(ValueError, match="doesn't fit"):
        generate_board_png((40, 70))
