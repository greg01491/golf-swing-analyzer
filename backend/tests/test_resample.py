import numpy as np
import pytest

from golf_sim.capture.frame import Frame
from golf_sim.capture.resample import resample_to_grid


def _frames(timestamps):
    return [
        Frame(timestamp=t, image=np.full((2, 2, 3), i % 256, np.uint8))
        for i, t in enumerate(timestamps)
    ]


def test_overdelivering_camera_resamples_to_exact_grid():
    # camera reading at ~2x real rate (duplicated frames), like the rig's camera 2
    frames = _frames(np.arange(0, 3.0, 1 / 122))
    out = resample_to_grid(frames, start_time=0.0, duration_s=3.0, fps=60)
    assert len(out) == 180
    assert out[0].timestamp == 0.0
    assert out[-1].timestamp == pytest.approx(179 / 60)


def test_underdelivering_camera_fills_grid_with_nearest():
    # dropped frames: only 30fps worth of real frames for a 60fps grid
    frames = _frames(np.arange(0, 1.0, 1 / 30))
    out = resample_to_grid(frames, start_time=0.0, duration_s=1.0, fps=60)
    assert len(out) == 60


def test_two_cameras_get_identical_frame_counts():
    fast = _frames(np.arange(0, 2.0, 1 / 122))
    slow = _frames(np.arange(0, 2.0, 1 / 59))
    out_fast = resample_to_grid(fast, 0.0, 2.0, fps=60)
    out_slow = resample_to_grid(slow, 0.0, 2.0, fps=60)
    assert len(out_fast) == len(out_slow) == 120


def test_nearest_frame_selection():
    frames = _frames([0.0, 0.5, 1.0])
    out = resample_to_grid(frames, start_time=0.0, duration_s=1.0, fps=2)
    # grid instants 0.0 and 0.5 -> frames 0 and 1
    assert out[0].image[0, 0, 0] == 0
    assert out[1].image[0, 0, 0] == 1


def test_empty_frames_raise():
    with pytest.raises(ValueError):
        resample_to_grid([], 0.0, 1.0, fps=30)
