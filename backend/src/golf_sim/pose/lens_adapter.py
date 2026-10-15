"""Keep Pose2Sim residuals in the same corrected-pixel space as its inputs."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np

_ADAPTER_LOCK = threading.RLock()


@contextmanager
def consistent_lens_reprojection(observation_support: list[bool] | None = None) -> Iterator[None]:
    import Pose2Sim.personAssociation as association
    import Pose2Sim.triangulation as triangulation
    from Pose2Sim.common import weighted_triangulation

    with _ADAPTER_LOCK:
        native_association = association.triangulate_comb
        native_triangulation = triangulation.triangulation_from_best_cameras

        def associate(combination, coordinates, projections, parameters, config):
            if not config.get("triangulation", {}).get("undistort_points", False):
                return native_association(combination, coordinates, projections, parameters, config)
            active = [index for index, person in enumerate(combination) if np.isfinite(person)]
            if len(active) < 2:
                return float("inf"), combination, np.array([np.nan, np.nan, np.nan, 1.0])
            observed = np.asarray([coordinates[index] for index in active])
            selected = [projections[index] for index in active]
            point = weighted_triangulation(selected, observed[:, 0], observed[:, 1], observed[:, 2])
            errors = []
            for index, projection in enumerate(selected):
                image = projection @ point
                if not np.isfinite(image).all() or image[2] <= 0:
                    return float("inf"), combination, point
                errors.append(np.linalg.norm(image[:2] / image[2] - observed[index, :2]))
            return float(np.mean(errors)), combination, point

        def triangulate(config, coordinates, swapped, projections, parameters):
            if config.get("triangulation", {}).get("undistort_points", False):
                parameters = {
                    **parameters,
                    "K": parameters["optim_K"],
                    "dist": [np.zeros_like(coefficients) for coefficients in parameters["dist"]],
                }
            result = native_triangulation(config, coordinates, swapped, projections, parameters)
            if observation_support is not None:
                observation_support.append(
                    bool(np.isfinite(result[0]).all() and np.isfinite(result[1]))
                )
            return result

        association.triangulate_comb = associate
        triangulation.triangulation_from_best_cameras = triangulate
        try:
            yield
        finally:
            association.triangulate_comb = native_association
            triangulation.triangulation_from_best_cameras = native_triangulation
