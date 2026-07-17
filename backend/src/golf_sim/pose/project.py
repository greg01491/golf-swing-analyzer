"""Maps our session folders onto the project layout Pose2Sim expects.

A session (written by golf_sim.capture.writer) is:

    <session>/camera_1.mp4, camera_2.mp4, metadata.json

Pose2Sim wants a project directory with a videos/ subfolder, and writes its
outputs to a pose/ subfolder next to it:

    <session>/pose2sim/videos/camera_1.mp4, camera_2.mp4   (input, copied)
    <session>/pose2sim/pose/camera_1_json/...              (output, per-frame)
    <session>/pose2sim/pose/camera_1_pose.mp4              (output, overlay)

Keeping Pose2Sim's native layout inside the session folder (rather than
converting to our own format) matters: the Phase 4 triangulation stages
consume this exact structure.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def prepare_pose_project(session_dir: Path) -> Path:
    """Build (or refresh) the Pose2Sim project folder for a session and
    return its path."""
    session_dir = Path(session_dir)
    clips = sorted(session_dir.glob("camera_*.mp4"))
    if not clips:
        raise FileNotFoundError(f"no camera_*.mp4 clips found in {session_dir}")

    project_dir = session_dir / "pose2sim"
    videos_dir = project_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    for clip in clips:
        target = videos_dir / clip.name
        if not target.exists() or target.stat().st_mtime < clip.stat().st_mtime:
            shutil.copy2(clip, target)

    _install_base_config(project_dir)
    return project_dir


def _install_base_config(project_dir: Path) -> None:
    """Copy Pose2Sim's packaged default Config.toml into the project.

    We drive Pose2Sim with config *dicts*, and dict overrides are merged over
    this file. But several stages (personAssociation, triangulation) also use
    the Config.toml's *location* to anchor their directory search -- without
    one in the project dir they fall back to os.getcwd() and fail to find the
    installed calibration folder.
    """
    target = project_dir / "Config.toml"
    if target.exists():
        return
    import Pose2Sim

    packaged_default = Path(Pose2Sim.__file__).parent / "Demo_SinglePerson" / "Config.toml"
    shutil.copy2(packaged_default, target)


def pose_output_dir(project_dir: Path) -> Path:
    return Path(project_dir) / "pose"


def landmark_json_dirs(project_dir: Path) -> list[Path]:
    """Per-camera folders of per-frame OpenPose-format landmark JSONs,
    present after poseEstimation has run."""
    return sorted(pose_output_dir(project_dir).glob("camera_*_json"))


def overlay_videos(project_dir: Path) -> list[Path]:
    return sorted(pose_output_dir(project_dir).glob("camera_*_pose.mp4"))
