import pytest

from golf_sim.pose.project import landmark_json_dirs, overlay_videos, prepare_pose_project


def _fake_session(tmp_path):
    session = tmp_path / "20260717T000000Z-abcd1234"
    session.mkdir()
    (session / "camera_1.mp4").write_bytes(b"fake-video-1")
    (session / "camera_2.mp4").write_bytes(b"fake-video-2")
    (session / "metadata.json").write_text("{}")
    return session


def test_prepare_pose_project_copies_clips_into_videos_dir(tmp_path):
    session = _fake_session(tmp_path)

    project_dir = prepare_pose_project(session)

    assert project_dir == session / "pose2sim"
    assert (project_dir / "videos" / "camera_1.mp4").read_bytes() == b"fake-video-1"
    assert (project_dir / "videos" / "camera_2.mp4").read_bytes() == b"fake-video-2"


def test_prepare_pose_project_is_idempotent(tmp_path):
    session = _fake_session(tmp_path)
    prepare_pose_project(session)
    project_dir = prepare_pose_project(session)
    assert sorted(p.name for p in (project_dir / "videos").iterdir()) == [
        "camera_1.mp4",
        "camera_2.mp4",
    ]


def test_prepare_pose_project_raises_on_empty_session(tmp_path):
    empty = tmp_path / "empty-session"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_pose_project(empty)


def test_output_helpers_find_pose_artifacts(tmp_path):
    session = _fake_session(tmp_path)
    project_dir = prepare_pose_project(session)

    pose_dir = project_dir / "pose"
    (pose_dir / "camera_1_json").mkdir(parents=True)
    (pose_dir / "camera_2_json").mkdir()
    (pose_dir / "camera_1_pose.mp4").write_bytes(b"")

    assert [d.name for d in landmark_json_dirs(project_dir)] == [
        "camera_1_json",
        "camera_2_json",
    ]
    assert [v.name for v in overlay_videos(project_dir)] == ["camera_1_pose.mp4"]
