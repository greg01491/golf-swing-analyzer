import cv2
import matplotlib
import numpy as np
import pytest

import golf_sim.pose.reconstruct as reconstruct
from golf_sim.pose.lens_adapter import consistent_lens_reprojection
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


def test_corrected_lens_adapter_recovers_known_point_and_restores_dependency_functions():
    triangulation = pytest.importorskip("Pose2Sim.triangulation")
    association = pytest.importorskip("Pose2Sim.personAssociation")
    native = triangulation.triangulation_from_best_cameras
    native_association = association.triangulate_comb
    matrix = np.array([[900.0, 0, 640], [0, 900, 360], [0, 0, 1]])
    distortion = np.array([-0.4, 0.15, 0.0, 0.0])
    translation = np.array([-1.5, 0.0, 0.0])
    point = np.array([[1.0, 0.8, 2.4]])
    corrected = []
    for shift in (np.zeros(3), translation):
        image, _ = cv2.projectPoints(point, np.zeros(3), shift, matrix, distortion)
        corrected.append(cv2.undistortPoints(image, matrix, distortion, P=matrix).reshape(2))
    coordinates = (
        np.array([item[0] for item in corrected]),
        np.array([item[1] for item in corrected]),
        np.ones(2),
    )
    projections = [
        matrix @ np.column_stack((np.eye(3), shift)) for shift in (np.zeros(3), translation)
    ]
    parameters = {
        "K": [matrix, matrix],
        "optim_K": [matrix, matrix],
        "dist": [distortion, distortion],
        "R": [np.zeros(3), np.zeros(3)],
        "T": [np.zeros(3), translation],
    }
    config = {
        "triangulation": {
            "undistort_points": True,
            "min_cameras_for_triangulation": 2,
            "reproj_error_threshold_triangulation": 15,
        }
    }
    with consistent_lens_reprojection():
        result = triangulation.triangulation_from_best_cameras(
            config, coordinates, coordinates, projections, parameters
        )
        assert result[0] == pytest.approx(point[0], abs=0.0001)
        observed = np.column_stack((np.asarray(corrected), np.ones(2)))
        error, _, associated = association.triangulate_comb(
            np.zeros(2), observed, projections, parameters, config
        )
        assert error < 0.01
        assert associated[:3] == pytest.approx(point[0], abs=0.0001)
    assert triangulation.triangulation_from_best_cameras is native
    assert association.triangulate_comb is native_association


def test_trc_reference_transform_matches_installed_pose2sim_basis():
    common = pytest.importorskip("Pose2Sim.common")
    import pandas as pd

    from golf_sim.pose.reconstruction_evidence import WORLD_TO_TRC

    points = np.array([[1.0, 2.0, 3.0], [-4.0, 5.0, 6.0]])
    converted = common.zup2yup(pd.DataFrame(points)).to_numpy()
    assert converted == pytest.approx(points @ WORLD_TO_TRC.T)
    assert converted @ WORLD_TO_TRC == pytest.approx(points)
