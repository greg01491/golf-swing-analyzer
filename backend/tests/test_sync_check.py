import numpy as np
import pytest

from golf_sim.capture.frame import Frame
from golf_sim.capture.sync_check import check_sync
from golf_sim.capture.writer import write_clip


def _clip_with_flash_at(path, flash_index: int, num_frames: int = 20, fps: float = 30.0):
    frames = []
    for i in range(num_frames):
        brightness = 200 if i == flash_index else 10
        image = np.full((16, 16, 3), brightness, dtype=np.uint8)
        frames.append(Frame(timestamp=i / fps, image=image))
    write_clip(frames, path, fps=fps)


def test_check_sync_detects_known_offset(tmp_path):
    fps = 30.0
    clip_a = tmp_path / "camera_a.mp4"
    clip_b = tmp_path / "camera_b.mp4"
    _clip_with_flash_at(clip_a, flash_index=10, fps=fps)
    _clip_with_flash_at(clip_b, flash_index=12, fps=fps)  # 2 frames later == 1/15s behind

    result = check_sync(clip_a, clip_b)

    assert result["camera_a"]["flash_frame"] == 10
    assert result["camera_b"]["flash_frame"] == 12
    assert result["offset_s"] == pytest.approx(-(2 / fps), abs=1e-3)
