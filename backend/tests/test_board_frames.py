import numpy as np

from golf_sim.capture.frame import Frame
from golf_sim.capture.writer import write_clip
from golf_sim.pose.board_frames import extract_extrinsics_frames, extract_intrinsics_frames


def _session_with_clips(tmp_path, name="2026-07-18_19-00-00_testcafe"):
    session = tmp_path / name
    session.mkdir()
    frames = [
        Frame(timestamp=i / 30, image=np.full((12, 16, 3), i * 10 % 256, np.uint8))
        for i in range(30)
    ]
    write_clip(frames, session / "camera_1.mp4", fps=30)
    write_clip(frames, session / "camera_2.mp4", fps=30)
    return session


def test_intrinsics_extraction_layout(tmp_path):
    session = _session_with_clips(tmp_path)
    rig = tmp_path / "calibration"

    extract_intrinsics_frames([session], rig, frames_per_clip=4)

    for cam in ["camera_1", "camera_2"]:
        images = list((rig / "intrinsics" / f"int_{cam}_img").glob("*.png"))
        assert len(images) == 4


def test_extrinsics_extraction_layout(tmp_path):
    session = _session_with_clips(tmp_path)
    rig = tmp_path / "calibration"

    extract_extrinsics_frames(session, rig)

    assert (rig / "extrinsics" / "camera_1_ext.png").exists()
    assert (rig / "extrinsics" / "camera_2_ext.png").exists()
