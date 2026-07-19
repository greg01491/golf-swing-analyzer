"""Generates a printable checkerboard PNG sized to match the currently
configured corner count (config.yaml calibration.checkerboard_corners),
served in-app so the calibration wizard is self-contained -- no separate
"here's a file to print" step outside the app.

Printed at a NOMINAL square size; real printers rarely reproduce exact
scale, so the wizard has the user measure the actual printed square with a
ruler and enter that instead of trusting this nominal value.
"""

from __future__ import annotations

import cv2
import numpy as np

_DPI = 300
_NOMINAL_SQUARE_MM = 30.0
_A4_PX = (2480, 3508)  # width, height at 300 DPI, portrait


def generate_board_png(corners_nb: tuple[int, int]) -> bytes:
    mm_to_px = _DPI / 25.4
    square_px = round(_NOMINAL_SQUARE_MM * mm_to_px)
    squares_across = corners_nb[0] + 1
    squares_down = corners_nb[1] + 1

    board_w, board_h = squares_across * square_px, squares_down * square_px
    page_w, page_h = _A4_PX
    if board_w > page_w or board_h > page_h:
        raise ValueError(
            f"a {squares_across}x{squares_down}-square board at {_NOMINAL_SQUARE_MM}mm/square "
            f"doesn't fit on A4 at {_DPI} DPI -- reduce calibration.checkerboard_corners"
        )

    page = np.full((page_h, page_w), 255, np.uint8)
    x0, y0 = (page_w - board_w) // 2, (page_h - board_h) // 2
    for r in range(squares_down):
        for c in range(squares_across):
            if (r + c) % 2 == 0:
                y, x = y0 + r * square_px, x0 + c * square_px
                page[y : y + square_px, x : x + square_px] = 0

    cv2.putText(
        page,
        "Golf Sim calibration board -- print at 100% scale (no fit-to-page)",
        (max(x0 - 100, 10), max(y0 - 40, 40)),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        0,
        2,
    )
    cv2.putText(
        page,
        "Measure one square with a ruler and enter the size in the wizard",
        (max(x0 - 100, 10), min(y0 + board_h + 60, page_h - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        0,
        2,
    )

    ok, buf = cv2.imencode(".png", page)
    if not ok:
        raise RuntimeError("failed to encode calibration board PNG")
    return buf.tobytes()
