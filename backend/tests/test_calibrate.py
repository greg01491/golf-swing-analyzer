import time

import pytest

from golf_sim.config import CalibrationConfig
from golf_sim.pose.calibrate import (
    CalibrationMissingError,
    calibration_status,
    install_calibration,
)


def _config(tmp_path, max_age_days=60):
    return CalibrationConfig(
        dir=str(tmp_path / "calibration"),
        max_age_days=max_age_days,
        checkerboard_corners=[4, 7],
        checkerboard_square_size_mm=60,
    )


def test_status_missing_when_no_calibration(tmp_path):
    status = calibration_status(_config(tmp_path))
    assert not status.exists
    assert status.recalibration_needed


def test_status_ok_for_fresh_calibration(tmp_path):
    config = _config(tmp_path)
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir()
    (calib_dir / "Calib_board.toml").write_text("[cam_01]\n")

    status = calibration_status(config)
    assert status.exists and not status.stale
    assert not status.recalibration_needed
    assert status.age_days == pytest.approx(0, abs=0.01)


def test_status_stale_for_old_calibration(tmp_path):
    config = _config(tmp_path, max_age_days=60)
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir()
    calib_file = calib_dir / "Calib_board.toml"
    calib_file.write_text("[cam_01]\n")
    old = time.time() - 90 * 86400
    import os

    os.utime(calib_file, (old, old))

    status = calibration_status(config)
    assert status.exists and status.stale
    assert status.recalibration_needed


def test_install_calibration_copies_into_project(tmp_path):
    config = _config(tmp_path)
    calib_dir = tmp_path / "calibration"
    calib_dir.mkdir()
    (calib_dir / "Calib_board.toml").write_text("[cam_01]\nname = 'camera_1'\n")
    project_dir = tmp_path / "session" / "pose2sim"
    project_dir.mkdir(parents=True)

    installed = install_calibration(project_dir, config)

    assert installed == project_dir / "calibration" / "Calib_board.toml"
    assert installed.read_text() == "[cam_01]\nname = 'camera_1'\n"


def test_install_calibration_raises_when_missing(tmp_path):
    project_dir = tmp_path / "session" / "pose2sim"
    project_dir.mkdir(parents=True)
    with pytest.raises(CalibrationMissingError):
        install_calibration(project_dir, _config(tmp_path))
