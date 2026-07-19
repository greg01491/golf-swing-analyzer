"""Runs Pose2Sim's 2D pose stage over a captured session (Phase 3).

Pose2Sim is imported lazily inside the function: it's an optional extra
(`pip install -e ".[pose]"`) and pulls in a heavy ML stack that the
capture/audio paths shouldn't depend on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from golf_sim.capture.transcode import ensure_h264
from golf_sim.config import PoseConfig
from golf_sim.pose.project import landmark_json_dirs, overlay_videos, prepare_pose_project


@dataclass
class PoseEstimationResult:
    project_dir: Path
    landmark_dirs: list[Path]
    overlay_videos: list[Path]


def run_pose_estimation(session_dir: Path, pose_config: PoseConfig) -> PoseEstimationResult:
    from Pose2Sim import Pose2Sim

    project_dir = prepare_pose_project(session_dir)

    config = {
        "project": {"project_dir": str(project_dir)},
        "pose": {
            "pose_model": pose_config.pose_model,
            "mode": pose_config.mode,
            # headless: no live cv2 window (would block/crash off-desktop)
            "display_detection": False,
            "save_video": "to_video" if pose_config.save_debug_video else "none",
        },
    }
    Pose2Sim.poseEstimation(config)

    # Pose2Sim writes the overlay videos through OpenCV too, so they're
    # mp4v -- unplayable in the app's Chromium player without this.
    for video in overlay_videos(project_dir):
        ensure_h264(video)

    result = PoseEstimationResult(
        project_dir=project_dir,
        landmark_dirs=landmark_json_dirs(project_dir),
        overlay_videos=overlay_videos(project_dir),
    )
    if not result.landmark_dirs:
        raise RuntimeError(
            f"Pose2Sim produced no landmark output under {project_dir / 'pose'} -- "
            "check the pose2sim logs above for errors"
        )
    return result
