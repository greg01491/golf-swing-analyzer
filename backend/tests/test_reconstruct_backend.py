import matplotlib
import pytest

import golf_sim.pose.reconstruct as reconstruct
from golf_sim.pose.reconstruct import preload_headless_pose_stack


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
