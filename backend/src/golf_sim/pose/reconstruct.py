"""3D reconstruction over a pose-estimated session (Phase 4, FR13/FR15).

Runs Pose2Sim's personAssociation -> triangulation -> filtering stages on a
session whose 2D pose stage has already run (golf_sim.pose.estimate). The
personAssociation stage matters even for a single-golfer setup: RTMPose
happily detects bystanders, and with multi_person=false Pose2Sim keeps only
the person with the lowest reprojection error across cameras.

Output: <session>/pose2sim/pose-3d/*.trc -- the 3D landmark sequence stored
with the session for reuse (FR15), which Phase 5's metrics engine consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from golf_sim.config import Config
from golf_sim.pose.calibrate import install_calibration
from golf_sim.pose.project import landmark_json_dirs


@dataclass
class ReconstructionResult:
    project_dir: Path
    trc_files: list[Path]


def trc_files(project_dir: Path) -> list[Path]:
    pose3d = Path(project_dir) / "pose-3d"
    return sorted(pose3d.glob("*.trc")) if pose3d.is_dir() else []


def run_reconstruction(session_dir: Path, config: Config) -> ReconstructionResult:
    from Pose2Sim import Pose2Sim

    project_dir = Path(session_dir) / "pose2sim"
    if not landmark_json_dirs(project_dir):
        raise FileNotFoundError(
            f"no 2D landmark output under {project_dir / 'pose'} -- run "
            "golf_sim.pose.estimate first"
        )

    install_calibration(project_dir, config.calibration)

    pose2sim_config = {
        "project": {
            "project_dir": str(project_dir),
            "multi_person": False,
            # 'auto' trims to the lowest-reprojection-error span, which can
            # silently drop the start/end of a swing; keep every frame and
            # let Phase 5 pick the swing window instead.
            "frame_range": "all",
        },
        "filtering": {"display_figures": False},
    }
    Pose2Sim.personAssociation(pose2sim_config)
    Pose2Sim.triangulation(pose2sim_config)
    Pose2Sim.filtering(pose2sim_config)

    result = ReconstructionResult(project_dir=project_dir, trc_files=trc_files(project_dir))
    if not result.trc_files:
        raise RuntimeError(
            f"triangulation produced no .trc output under {project_dir / 'pose-3d'} -- "
            "check the Pose2Sim logs above"
        )
    return result
