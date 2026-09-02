import sys
import types
from pathlib import Path

import pytest

from golf_sim.pose.project import (
    _find_packaged_config,
    landmark_json_dirs,
    overlay_videos,
    prepare_pose_project,
)


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


def test_prepare_pose_project_installs_base_config_when_pose2sim_available(tmp_path):
    pytest.importorskip("Pose2Sim")
    session = _fake_session(tmp_path)

    project_dir = prepare_pose_project(session)

    # see _install_base_config: Pose2Sim stages anchor directory search on
    # this file's location, so it must exist in every project
    assert (project_dir / "Config.toml").exists()


def test_prepare_pose_project_raises_on_empty_session(tmp_path):
    empty = tmp_path / "empty-session"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        prepare_pose_project(empty)


def _fake_pose2sim(monkeypatch, root):
    """Point `import Pose2Sim` at a throwaway package root."""
    root.mkdir(parents=True, exist_ok=True)
    module = types.ModuleType("Pose2Sim")
    module.__file__ = str(root / "__init__.py")
    monkeypatch.setitem(sys.modules, "Pose2Sim", module)
    return root


def test_base_config_is_found_in_the_single_person_demo(tmp_path, monkeypatch):
    root = _fake_pose2sim(monkeypatch, tmp_path / "Pose2Sim")
    (root / "Demo_SinglePerson").mkdir()
    (root / "Demo_SinglePerson" / "Config.toml").write_text("# single")

    assert _find_packaged_config(root) == root / "Demo_SinglePerson" / "Config.toml"


def test_base_config_falls_back_when_the_preferred_demo_is_absent(tmp_path, monkeypatch):
    root = _fake_pose2sim(monkeypatch, tmp_path / "Pose2Sim")
    (root / "SomeOtherLayout").mkdir()
    (root / "SomeOtherLayout" / "Config.toml").write_text("# fallback")

    assert _find_packaged_config(root) == root / "SomeOtherLayout" / "Config.toml"


def test_missing_bundled_config_reports_the_packaging_cause(tmp_path, monkeypatch):
    """Regression: the packaged build stripped every Pose2Sim Demo_* file,
    so calibration died deep inside shutil with a bare FileNotFoundError.
    A missing base config must name the real cause instead."""
    root = _fake_pose2sim(monkeypatch, tmp_path / "Pose2Sim")
    assert _find_packaged_config(root) is None

    session = _fake_session(tmp_path)
    with pytest.raises(FileNotFoundError, match="golf_sim_backend.spec"):
        prepare_pose_project(session)


def test_spec_keeps_pose2sim_demo_configs_out_of_the_media_filter():
    """The Demo_* filter exists to drop ~26MB of demo videos. It must not
    also drop the 130KB of Config.toml files calibration depends on."""
    spec = (
        Path(__file__).resolve().parents[1] / "golf_sim_backend.spec"
    ).read_text(encoding="utf-8")

    assert 'KEEP_DEMO_SUFFIXES = {".toml"}' in spec
    assert "Path(src).suffix.lower() not in KEEP_DEMO_SUFFIXES" in spec


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
