import sys
import types

import matplotlib
import pytest

import golf_sim.pose.reconstruct as reconstruct
from golf_sim.pose.reconstruct import (
    SwingNotVisibleError,
    preload_headless_pose_stack,
    run_reconstruction,
)


def _stub_pose2sim(monkeypatch, triangulation):
    """Installs a fake Pose2Sim so reconstruction runs without the real stack."""
    inner = types.SimpleNamespace(
        personAssociation=lambda cfg: None,
        triangulation=triangulation,
        filtering=lambda cfg: None,
    )
    package = types.ModuleType("Pose2Sim")
    package.Pose2Sim = inner
    monkeypatch.setitem(sys.modules, "Pose2Sim", package)

    monkeypatch.setattr(reconstruct, "_headless_ready", True)
    monkeypatch.setattr(reconstruct, "landmark_json_dirs", lambda project_dir: ["camera_1_json"])
    monkeypatch.setattr(reconstruct, "install_calibration", lambda project_dir, calib: None)


def test_untriangulated_swing_does_not_blame_a_good_calibration(monkeypatch, tmp_path):
    """Pose2Sim blames calibration/sync/Config.toml for what is really a
    framing problem, which sends the golfer off to redo a calibration that is
    fine (seen live at 0.2px reprojection)."""

    def boom(cfg):
        raise Exception(
            "No persons have been triangulated. Please check your calibration "
            "and your synchronization, or the triangulation parameters in Config.toml."
        )

    _stub_pose2sim(monkeypatch, boom)

    with pytest.raises(SwingNotVisibleError) as excinfo:
        run_reconstruction(tmp_path, config=types.SimpleNamespace(calibration=None))

    message = str(excinfo.value)
    assert "Config.toml" not in message
    assert "both cameras" in message
    assert "no need to redo it" in message


def test_other_triangulation_failures_are_not_swallowed(monkeypatch, tmp_path):
    def boom(cfg):
        raise ValueError("some other triangulation problem")

    _stub_pose2sim(monkeypatch, boom)

    with pytest.raises(ValueError, match="some other triangulation problem"):
        run_reconstruction(tmp_path, config=types.SimpleNamespace(calibration=None))


def test_preload_forces_headless_agg_backend():
    # Needs the pose extra (imports Pose2Sim.filtering for its side effect);
    # skip cleanly in the dev-only CI environment.
    pytest.importorskip("Pose2Sim")

    # Start from a different (but always-available, no GUI toolkit required)
    # backend so the assertion proves the switch happened, not that Agg
    # merely happened to already be active.
    matplotlib.use("pdf")
    reconstruct._headless_ready = False  # re-arm the once-only guard for the test
    try:
        preload_headless_pose_stack()
        # Pose2Sim.filtering flips the backend to qtagg at import; the preload
        # must force it back to headless Agg so worker-thread figure ops that
        # follow can't deadlock on Qt.
        assert matplotlib.get_backend().lower() == "agg"
    finally:
        reconstruct._headless_ready = False
