"""Rig calibration management (Phase 4, FR13/FR14).

The two-camera rig is calibrated once (checkerboard workflow via Pose2Sim)
and the resulting Calib*.toml lives centrally in config/calibration/. Each
session's Pose2Sim project gets a copy installed before triangulation.
Cameras are matched to calibration entries by sorted order, so the rig
calibration must list cameras in the same order as the session clips
(camera_1, camera_2).
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from golf_sim.config import REPO_ROOT, CalibrationConfig


class CalibrationMissingError(RuntimeError):
    pass


# A calibration whose recorded reprojection error exceeds this is broken and
# will produce garbage 3D; flagged so the UI can tell the user to recalibrate.
_BROKEN_REPROJ_PX = 50.0


@dataclass
class CalibrationStatus:
    exists: bool
    file: Path | None
    age_days: float | None
    stale: bool
    reprojection_error_px: float | None = None

    @property
    def broken(self) -> bool:
        return (
            self.reprojection_error_px is not None
            and self.reprojection_error_px > _BROKEN_REPROJ_PX
        )

    @property
    def recalibration_needed(self) -> bool:
        return not self.exists or self.stale or self.broken


def _read_reprojection_error(calib_file: Path) -> float | None:
    try:
        for line in calib_file.read_text().splitlines():
            if line.strip().startswith("mean_reprojection_error_px"):
                return float(line.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    return None


def _rig_dir(calibration_config: CalibrationConfig) -> Path:
    path = Path(calibration_config.dir)
    return path if path.is_absolute() else REPO_ROOT / path


def _find_calib_file(rig_dir: Path) -> Path | None:
    candidates = sorted(rig_dir.glob("Calib*.toml"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def calibration_status(calibration_config: CalibrationConfig) -> CalibrationStatus:
    rig_dir = _rig_dir(calibration_config)
    calib_file = _find_calib_file(rig_dir) if rig_dir.is_dir() else None
    if calib_file is None:
        return CalibrationStatus(exists=False, file=None, age_days=None, stale=False)
    age_days = (time.time() - calib_file.stat().st_mtime) / 86400
    return CalibrationStatus(
        exists=True,
        file=calib_file,
        age_days=age_days,
        stale=age_days > calibration_config.max_age_days,
        reprojection_error_px=_read_reprojection_error(calib_file),
    )


def install_calibration(project_dir: Path, calibration_config: CalibrationConfig) -> Path:
    """Copy the rig calibration into a session project's calibration/ folder
    (where Pose2Sim's triangulation stage looks for it)."""
    status = calibration_status(calibration_config)
    if not status.exists:
        raise CalibrationMissingError(
            f"no Calib*.toml found in {_rig_dir(calibration_config)} -- run the "
            "calibration workflow first (see golf_sim.pose.cli calibrate)"
        )
    target_dir = Path(project_dir) / "calibration"
    target_dir.mkdir(parents=True, exist_ok=True)
    assert status.file is not None
    target = target_dir / status.file.name
    shutil.copy2(status.file, target)
    return target


def run_checkerboard_calibration(calibration_config: CalibrationConfig) -> Path:
    """Compute rig calibration from checkerboard footage via Pose2Sim.

    Expects the user to have recorded the checkerboard with both cameras and
    placed the footage in the rig calibration directory following Pose2Sim's
    layout:

        config/calibration/intrinsics/int_camera_1_img/*.jpg|mp4
        config/calibration/intrinsics/int_camera_2_img/*.jpg|mp4
        config/calibration/extrinsics/camera_1_ext.png|mp4
        config/calibration/extrinsics/camera_2_ext.png|mp4

    Writes Calib*.toml into the rig calibration dir and returns its path.
    """
    from Pose2Sim import Pose2Sim

    rig_dir = _rig_dir(calibration_config)
    if not (rig_dir / "intrinsics").is_dir():
        raise CalibrationMissingError(
            f"no intrinsics/ folder under {rig_dir} -- record checkerboard "
            "footage per camera first (see this function's docstring for layout)"
        )

    # Pose2Sim's calibration stage reads <project>/calibration/, so present
    # the rig dir's *parent* as a project whose calibration folder is rig_dir.
    if rig_dir.name != "calibration":
        raise ValueError(
            f"rig calibration dir must be named 'calibration' (got {rig_dir}) "
            "so Pose2Sim's project layout maps onto it"
        )
    project_dir = rig_dir.parent

    corners = calibration_config.checkerboard_corners
    square = calibration_config.checkerboard_square_size_mm
    config = {
        "project": {"project_dir": str(project_dir)},
        "calibration": {
            "calibration_type": "calculate",
            "calculate": {
                "intrinsics": {
                    "intrinsics_corners_nb": corners,
                    "intrinsics_square_size": square,
                },
                "extrinsics": {
                    "extrinsics_method": "board",
                    "board": {
                        "extrinsics_corners_nb": corners,
                        "extrinsics_square_size": square,
                    },
                    "show_reprojection_error": False,
                },
            },
        },
    }
    Pose2Sim.calibration(config)

    calib_file = _find_calib_file(rig_dir)
    if calib_file is None:
        raise RuntimeError(f"calibration ran but produced no Calib*.toml in {rig_dir}")
    return calib_file
