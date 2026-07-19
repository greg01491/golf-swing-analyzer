import cv2
import numpy as np
import pytest

from golf_sim.pose.board_image import generate_board_png


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
