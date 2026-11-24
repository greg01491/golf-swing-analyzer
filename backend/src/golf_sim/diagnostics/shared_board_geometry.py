"""Fit and validate a camera-pair diagnostic from separate rigid-board placements."""

from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np

from golf_sim.pose.board_detect import detect_board_corners

_PATTERN = (4, 7)
_ORDERINGS = (np.arange(28), np.arange(27, -1, -1))


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _relative_rotation(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    return second @ first.T


def _rotation_distance(first: np.ndarray, second: np.ndarray) -> float:
    cosine = np.clip((np.trace(first @ second.T) - 1.0) / 2.0, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def _board_pose_options(
    image_points: np.ndarray, camera: dict, object_points: np.ndarray
) -> list[dict]:
    options = []
    for ordering_index, ordering in enumerate(_ORDERINGS):
        ok, rotation, translation = cv2.solvePnP(
            object_points,
            image_points[ordering],
            np.asarray(camera["matrix"], dtype=float),
            np.asarray(camera["distortions"], dtype=float),
        )
        if not ok:
            continue
        rotation_matrix = cv2.Rodrigues(rotation)[0]
        translation = translation.reshape(3)
        depths = (object_points @ rotation_matrix.T + translation)[:, 2]
        projected, _ = cv2.projectPoints(
            object_points,
            rotation,
            translation,
            np.asarray(camera["matrix"], dtype=float),
            np.asarray(camera["distortions"], dtype=float),
        )
        errors = np.linalg.norm(projected.reshape(-1, 2) - image_points[ordering], axis=1)
        if np.all(depths > 0) and np.isfinite(errors).all():
            options.append(
                {
                    "ordering": ordering_index,
                    "rotation": rotation_matrix,
                    "translation": translation,
                    "median_px": float(np.median(errors)),
                    "p95_px": float(np.percentile(errors, 95)),
                }
            )
    return options


def _project_error(
    points_camera_1: np.ndarray,
    observed: np.ndarray,
    camera: dict,
    ordering: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rotation = np.asarray(camera["rotation"], dtype=float)
    translation = np.asarray(camera["translation"], dtype=float)
    projected, _ = cv2.projectPoints(
        points_camera_1,
        rotation,
        translation,
        np.asarray(camera["matrix"], dtype=float),
        np.asarray(camera["distortions"], dtype=float),
    )
    depths = (points_camera_1 @ cv2.Rodrigues(rotation)[0].T + translation)[:, 2]
    errors = np.linalg.norm(projected.reshape(-1, 2) - observed[ordering], axis=1)
    return errors, depths


def _direction_report(errors: list[np.ndarray], positive: list[np.ndarray], limit: float) -> dict:
    all_errors = np.concatenate(errors) if errors else np.array([])
    all_positive = np.concatenate(positive) if positive else np.array([], dtype=bool)
    return {
        "count": int(all_errors.size),
        "median_px": float(np.median(all_errors)) if all_errors.size else None,
        "p95_px": float(np.percentile(all_errors, 95)) if all_errors.size else None,
        "within_existing_limit_fraction": (
            float(np.mean(all_errors <= limit)) if all_errors.size else 0.0
        ),
        "positive_depth_fraction": float(np.mean(all_positive)) if all_positive.size else 0.0,
    }


def evaluate_shared_board_placements(
    placements: list[dict],
    calibration: dict,
    *,
    square_size_m: float,
    measured_baseline_m: float,
    fit_count: int,
    max_baseline_relative_error: float,
    max_tail_error_px: float = 15.0,
) -> dict:
    """Use whole captures for fitting/holdout and report both cross-view directions."""
    if not np.isfinite(square_size_m) or square_size_m <= 0:
        raise ValueError("checkerboard square size must be finite and positive")
    if (
        not np.isfinite(measured_baseline_m)
        or measured_baseline_m <= 0
        or not 0 <= max_baseline_relative_error < 1
    ):
        raise ValueError("measured baseline and relative scale tolerance must be valid")
    if len(placements) < 2 or not 1 <= fit_count < len(placements):
        raise ValueError("need separate nonempty fit and held-out placement groups")
    object_points = np.zeros((28, 3), np.float32)
    object_points[:, :2] = np.mgrid[0:4, 0:7].T.reshape(-1, 2) * square_size_m
    prepared = []
    for item in placements:
        first = np.asarray(item["camera_1"], dtype=float)
        second = np.asarray(item["camera_2"], dtype=float)
        if first.shape != (28, 2) or second.shape != (28, 2):
            raise ValueError(
                "each placement must contain exactly 28 paired image corners per camera"
            )
        first_options = _board_pose_options(first, calibration["camera_1"], object_points)
        second_options = _board_pose_options(second, calibration["camera_2"], object_points)
        if not first_options or not second_options:
            raise ValueError(f"board pose lacks positive-depth PnP in both views: {item['id']}")
        candidates = []
        for one in first_options:
            for two in second_options:
                rotation = _relative_rotation(one["rotation"], two["rotation"])
                translation = two["translation"] - rotation @ one["translation"]
                baseline = float(np.linalg.norm(translation))
                relative_error = abs(baseline - measured_baseline_m) / measured_baseline_m
                candidates.append(
                    {
                        "rotation": rotation,
                        "translation": translation,
                        "baseline": baseline,
                        "baseline_relative_error": relative_error,
                        "one": one,
                        "two": two,
                    }
                )
        scale_supported = [
            candidate
            for candidate in candidates
            if candidate["baseline_relative_error"] <= max_baseline_relative_error
        ]
        if not scale_supported:
            raise ValueError(
                f"no checkerboard corner ordering agrees with the independently measured "
                f"baseline in placement {item['id']}"
            )
        prepared.append({**item, "first": first, "second": second, "candidates": scale_supported})

    fit = prepared[:fit_count]
    heldout = prepared[fit_count:]
    best = None
    for seed_placement in fit:
        for seed in seed_placement["candidates"]:
            selected, scores = [], []
            for placement in fit:
                candidate = min(
                    placement["candidates"],
                    key=lambda value: _rotation_distance(value["rotation"], seed["rotation"])
                    + 30 * np.linalg.norm(value["translation"] - seed["translation"]),
                )
                score = _rotation_distance(candidate["rotation"], seed["rotation"])
                score += 30 * np.linalg.norm(candidate["translation"] - seed["translation"])
                selected.append(candidate)
                scores.append(float(score))
            key = (float(np.median(scores)), float(np.percentile(scores, 90)))
            if best is None or key < best["key"]:
                best = {"key": key, "selected": selected}

    rotations = np.sum([item["rotation"] for item in best["selected"]], axis=0)
    u, _, vt = np.linalg.svd(rotations)
    correction = np.eye(3)
    correction[2, 2] = np.linalg.det(u @ vt)
    fitted_rotation = u @ correction @ vt
    fitted_translation = np.median([item["translation"] for item in best["selected"]], axis=0)
    fit_rotation_spread = [
        _rotation_distance(item["rotation"], fitted_rotation) for item in best["selected"]
    ]
    fit_translation_spread = [
        float(np.linalg.norm(item["translation"] - fitted_translation)) for item in best["selected"]
    ]

    reverse_rotation = fitted_rotation.T
    reverse_translation = -reverse_rotation @ fitted_translation
    heldout_first_to_second, heldout_second_to_first = [], []
    heldout_first_depths, heldout_second_depths = [], []
    active_first_to_second, active_second_to_first = [], []
    active_first_depths, active_second_depths = [], []
    active_best_first_to_second, active_best_second_to_first = [], []
    active_best_first_depths, active_best_second_depths = [], []
    heldout_details = []
    active_rotation = cv2.Rodrigues(np.asarray(calibration["camera_2"]["rotation"], dtype=float))[0]
    active_translation = np.asarray(calibration["camera_2"]["translation"], dtype=float)
    active_reverse_rotation = active_rotation.T
    active_reverse_translation = -active_reverse_rotation @ active_translation
    for placement in heldout:
        best_forward, best_reverse = None, None
        best_active_forward, best_active_reverse = None, None
        for one in placement["candidates"]:
            points_camera_1 = object_points @ one["one"]["rotation"].T + one["one"]["translation"]
            forward_projected, _ = cv2.projectPoints(
                points_camera_1 @ fitted_rotation.T + fitted_translation,
                np.zeros(3),
                np.zeros(3),
                np.asarray(calibration["camera_2"]["matrix"], dtype=float),
                np.asarray(calibration["camera_2"]["distortions"], dtype=float),
            )
            forward_depth = (points_camera_1 @ fitted_rotation.T + fitted_translation)[:, 2] > 0
            for order in _ORDERINGS:
                errors = np.linalg.norm(
                    forward_projected.reshape(-1, 2) - placement["second"][order], axis=1
                )
                candidate = (
                    not bool(np.all(forward_depth)),
                    float(np.percentile(errors, 95)),
                    float(np.median(errors)),
                    errors,
                    forward_depth,
                    one,
                    order,
                )
                if best_forward is None or candidate[:3] < best_forward[:3]:
                    best_forward = candidate

            active_forward_points = points_camera_1 @ active_rotation.T + active_translation
            active_forward_projected, _ = cv2.projectPoints(
                active_forward_points,
                np.zeros(3),
                np.zeros(3),
                np.asarray(calibration["camera_2"]["matrix"], dtype=float),
                np.asarray(calibration["camera_2"]["distortions"], dtype=float),
            )
            active_forward_depth = active_forward_points[:, 2] > 0
            for order in _ORDERINGS:
                errors = np.linalg.norm(
                    active_forward_projected.reshape(-1, 2) - placement["second"][order],
                    axis=1,
                )
                candidate = (
                    not bool(np.all(active_forward_depth)),
                    float(np.percentile(errors, 95)),
                    float(np.median(errors)),
                    errors,
                    active_forward_depth,
                )
                if best_active_forward is None or candidate[:3] < best_active_forward[:3]:
                    best_active_forward = candidate

            points_camera_2 = object_points @ one["two"]["rotation"].T + one["two"]["translation"]
            reverse_points = points_camera_2 @ reverse_rotation.T + reverse_translation
            reverse_projected, _ = cv2.projectPoints(
                reverse_points,
                np.zeros(3),
                np.zeros(3),
                np.asarray(calibration["camera_1"]["matrix"], dtype=float),
                np.asarray(calibration["camera_1"]["distortions"], dtype=float),
            )
            reverse_depth = reverse_points[:, 2] > 0
            for order in _ORDERINGS:
                errors = np.linalg.norm(
                    reverse_projected.reshape(-1, 2) - placement["first"][order], axis=1
                )
                candidate = (
                    not bool(np.all(reverse_depth)),
                    float(np.percentile(errors, 95)),
                    float(np.median(errors)),
                    errors,
                    reverse_depth,
                    one,
                    order,
                )
                if best_reverse is None or candidate[:3] < best_reverse[:3]:
                    best_reverse = candidate

            active_reverse_points = points_camera_2 @ active_reverse_rotation.T
            active_reverse_points += active_reverse_translation
            active_reverse_projected, _ = cv2.projectPoints(
                active_reverse_points,
                np.zeros(3),
                np.zeros(3),
                np.asarray(calibration["camera_1"]["matrix"], dtype=float),
                np.asarray(calibration["camera_1"]["distortions"], dtype=float),
            )
            active_reverse_depth = active_reverse_points[:, 2] > 0
            for order in _ORDERINGS:
                errors = np.linalg.norm(
                    active_reverse_projected.reshape(-1, 2) - placement["first"][order],
                    axis=1,
                )
                candidate = (
                    not bool(np.all(active_reverse_depth)),
                    float(np.percentile(errors, 95)),
                    float(np.median(errors)),
                    errors,
                    active_reverse_depth,
                )
                if best_active_reverse is None or candidate[:3] < best_active_reverse[:3]:
                    best_active_reverse = candidate

        heldout_first_to_second.append(best_forward[3])
        heldout_second_to_first.append(best_reverse[3])
        heldout_first_depths.append(best_forward[4])
        heldout_second_depths.append(best_reverse[4])
        active_points_camera_1 = (
            object_points @ best_forward[5]["one"]["rotation"].T
            + best_forward[5]["one"]["translation"]
        )
        active_forward_points = active_points_camera_1 @ active_rotation.T + active_translation
        active_forward_projected, _ = cv2.projectPoints(
            active_forward_points,
            np.zeros(3),
            np.zeros(3),
            np.asarray(calibration["camera_2"]["matrix"], dtype=float),
            np.asarray(calibration["camera_2"]["distortions"], dtype=float),
        )
        active_forward_errors = np.linalg.norm(
            active_forward_projected.reshape(-1, 2) - placement["second"][best_forward[6]],
            axis=1,
        )
        active_forward_depth = active_forward_points[:, 2] > 0
        active_points_camera_2 = (
            object_points @ best_reverse[5]["two"]["rotation"].T
            + best_reverse[5]["two"]["translation"]
        )
        active_reverse_points = (
            active_points_camera_2 @ active_reverse_rotation.T + active_reverse_translation
        )
        active_reverse_projected, _ = cv2.projectPoints(
            active_reverse_points,
            np.zeros(3),
            np.zeros(3),
            np.asarray(calibration["camera_1"]["matrix"], dtype=float),
            np.asarray(calibration["camera_1"]["distortions"], dtype=float),
        )
        active_reverse_errors = np.linalg.norm(
            active_reverse_projected.reshape(-1, 2) - placement["first"][best_reverse[6]],
            axis=1,
        )
        active_reverse_depth = active_reverse_points[:, 2] > 0
        active_first_to_second.append(active_forward_errors)
        active_second_to_first.append(active_reverse_errors)
        active_first_depths.append(active_forward_depth)
        active_second_depths.append(active_reverse_depth)
        active_best_first_to_second.append(best_active_forward[3])
        active_best_second_to_first.append(best_active_reverse[3])
        active_best_first_depths.append(best_active_forward[4])
        active_best_second_depths.append(best_active_reverse[4])
        heldout_details.append(
            {
                "id": placement["id"],
                "camera_1_to_camera_2_p95_px": best_forward[1],
                "camera_1_to_camera_2_positive_depth_fraction": float(np.mean(best_forward[4])),
                "camera_2_to_camera_1_p95_px": best_reverse[1],
                "camera_2_to_camera_1_positive_depth_fraction": float(np.mean(best_reverse[4])),
                "active_camera_1_to_camera_2_p95_px": float(
                    np.percentile(active_forward_errors, 95)
                ),
                "active_camera_2_to_camera_1_p95_px": float(
                    np.percentile(active_reverse_errors, 95)
                ),
                "active_best_order_camera_1_to_camera_2_p95_px": best_active_forward[1],
                "active_best_order_camera_2_to_camera_1_p95_px": best_active_reverse[1],
            }
        )

    return {
        "diagnostic_only": True,
        "candidate_for_activation": False,
        "physical_accuracy_certified": False,
        "fit_placements": [item["id"] for item in fit],
        "heldout_placements": [item["id"] for item in heldout],
        "checkerboard_square_size_m": square_size_m,
        "measured_baseline_m": measured_baseline_m,
        "fitted_baseline_m": float(np.linalg.norm(fitted_translation)),
        "baseline_relative_error": float(
            abs(np.linalg.norm(fitted_translation) - measured_baseline_m) / measured_baseline_m
        ),
        "baseline_within_existing_scale_tolerance": bool(
            abs(np.linalg.norm(fitted_translation) - measured_baseline_m) / measured_baseline_m
            <= max_baseline_relative_error
        ),
        "fitted_rotation_delta_from_active_deg": _rotation_distance(
            fitted_rotation, active_rotation
        ),
        "diagnostic_pose": {
            "camera_2_rotation_rodrigues": cv2.Rodrigues(fitted_rotation)[0].reshape(3).tolist(),
            "camera_2_translation_m": fitted_translation.tolist(),
        },
        "fit_rotation_spread_p95_deg": float(np.percentile(fit_rotation_spread, 95)),
        "fit_translation_spread_p95_m": float(np.percentile(fit_translation_spread, 95)),
        "heldout_camera_1_to_camera_2": _direction_report(
            heldout_first_to_second, heldout_first_depths, max_tail_error_px
        ),
        "heldout_camera_2_to_camera_1": _direction_report(
            heldout_second_to_first, heldout_second_depths, max_tail_error_px
        ),
        "active_heldout_camera_1_to_camera_2": _direction_report(
            active_first_to_second, active_first_depths, max_tail_error_px
        ),
        "active_heldout_camera_2_to_camera_1": _direction_report(
            active_second_to_first, active_second_depths, max_tail_error_px
        ),
        "active_best_order_heldout_camera_1_to_camera_2": _direction_report(
            active_best_first_to_second, active_best_first_depths, max_tail_error_px
        ),
        "active_best_order_heldout_camera_2_to_camera_1": _direction_report(
            active_best_second_to_first, active_best_second_depths, max_tail_error_px
        ),
        "heldout_per_placement": heldout_details,
        "timing_verified": False,
        "warning": (
            "This board diagnostic does not verify exposure synchronization, ground reference, "
            "or anatomical metric accuracy."
        ),
    }


def extract_board_placement(
    session_dir: Path, camera_calibration: dict, square_size_m: float
) -> dict:
    """Extract one middle-frame board pose from a stationary capture, read-only."""
    session_dir = Path(session_dir)
    observations = {}
    details = {}
    for role in ("camera_1", "camera_2"):
        video = session_dir / f"{role}.mp4"
        cap = cv2.VideoCapture(str(video), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
        try:
            if not cap.isOpened():
                raise ValueError(f"cannot open paired board clip {video}")
            count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            index = count // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f"cannot read middle board frame for {role}")
            corners = detect_board_corners(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), _PATTERN)
            if corners is None:
                raise ValueError(f"full checkerboard is not detected in {role} at frame {index}")
            points = corners.reshape(-1, 2)
            if np.linalg.norm(np.ptp(points, axis=0)) < 80:
                raise ValueError(f"checkerboard span in {role} is below 80 px")
            observations[role] = points
            details[role] = {
                "frame_index": index,
                "width": image.shape[1],
                "height": image.shape[0],
                "board_span_px": float(np.linalg.norm(np.ptp(points, axis=0))),
            }
        finally:
            cap.release()
    return {"id": session_dir.name, **details, **observations}
