"""Clips must come out H.264 (avc1): OpenCV can only write mp4v, which
Chromium/Electron cannot decode -- every session played as a black frame in
the app until write_clip started transcoding via the bundled ffmpeg."""

import numpy as np

from golf_sim.capture.frame import Frame
from golf_sim.capture.transcode import ensure_h264
from golf_sim.capture.writer import write_clip


def _codec_tags(path):
    data = path.read_bytes()
    return {tag for tag in (b"avc1", b"mp4v") if tag in data}


def test_write_clip_produces_h264(tmp_path):
    frames = [
        Frame(timestamp=i / 30, image=np.full((48, 64, 3), i * 10, np.uint8)) for i in range(10)
    ]
    out = tmp_path / "clip.mp4"
    write_clip(frames, out, fps=30)
    assert _codec_tags(out) == {b"avc1"}


def test_ensure_h264_leaves_original_on_bad_input(tmp_path):
    bogus = tmp_path / "not_a_video.mp4"
    bogus.write_bytes(b"this is not an mp4")
    assert ensure_h264(bogus) is False
    assert bogus.read_bytes() == b"this is not an mp4"
