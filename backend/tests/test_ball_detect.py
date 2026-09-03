import numpy as np

from golf_sim.analysis.ball_detect import (
    ball_present,
    detect_impact_by_disappearance,
    find_ball_at_address,
)


def _frame(with_ball: bool = True) -> np.ndarray:
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[:] = (40, 120, 40)
    if with_ball:
        # Bright orange ball in HSV-friendly BGR.
        frame = frame.copy()
        frame[150:162, 130:142] = (0, 140, 255)
    return frame


def test_find_ball_at_address_detects_coloured_circle():
    frame = _frame(True)
    ball = find_ball_at_address(
        frame,
        wrist_xy=(120.0, 90.0),
        hue_range=(5, 35),
        roi_offsets=(-20, 60, 40, 120),
        min_saturation=50,
        min_value=50,
        min_circularity=0.4,
        min_area_px=20,
    )

    assert ball is not None
    cx, cy, radius = ball
    assert 120 <= cx <= 150
    assert 140 <= cy <= 170
    assert radius > 4


def test_ball_present_turns_false_when_ball_is_removed():
    frame = _frame(True)
    ball = find_ball_at_address(
        frame,
        wrist_xy=(120.0, 90.0),
        hue_range=(5, 35),
        roi_offsets=(-20, 60, 40, 120),
        min_saturation=50,
        min_value=50,
        min_circularity=0.4,
        min_area_px=20,
    )
    assert ball is not None
    assert ball_present(
        frame,
        (ball[0], ball[1]),
        ball[2],
        (5, 35),
        min_saturation=50,
        min_value=50,
        present_min_fraction=0.1,
    )

    missing = _frame(False)
    assert not ball_present(
        missing,
        (ball[0], ball[1]),
        ball[2],
        (5, 35),
        min_saturation=50,
        min_value=50,
        present_min_fraction=0.1,
    )


def test_detect_impact_by_disappearance_uses_consecutive_missing_frames(tmp_path):
    import cv2

    video_path = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (320, 240))
    try:
        for _ in range(4):
            writer.write(_frame(True))
        writer.write(_frame(False))
        writer.write(_frame(False))
        writer.write(_frame(False))
    finally:
        writer.release()

    impact = detect_impact_by_disappearance(
        video_path,
        (136.0, 156.0),
        start_frame=0,
        fps=30.0,
        radius=6.0,
        hue_range=(5, 35),
        min_saturation=50,
        min_value=50,
        present_min_fraction=0.1,
        confirm_frames=2,
        search_seconds=1.0,
    )

    assert impact == 4
