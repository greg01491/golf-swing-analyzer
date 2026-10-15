"""Measured board-plane validation in the accepted camera calibration frame."""

from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from golf_sim.config import CalibrationValidationConfig, Config, resolve_state_path
from golf_sim.pose.board_detect import detect_board_corners
from golf_sim.pose.calibration_bundle import (
    activation_guard,
    atomic_json,
    camera_signatures,
    compare_signatures,
    fingerprint,
    load_active_bundle,
)
from golf_sim.pose.rig_calibration import CalibrationDataError


def solve_ground_reference(
    calibration: dict,
    observations: list[dict],
    corners: tuple[int, int],
    square_size_m: float,
    golfer_side: int,
    settings: CalibrationValidationConfig,
) -> dict:
    if golfer_side not in (-1, 1) or not np.isfinite(square_size_m) or square_size_m <= 0:
        raise CalibrationDataError(
            "ground reference requires a measured board and confirmed golfer side"
        )
    captures = sorted({item["capture"] for item in observations})
    if len(captures) < 2:
        raise CalibrationDataError("ground validation requires two independent board placements")
    columns, rows = corners
    if columns < 2 or rows < 2:
        raise CalibrationDataError(
            "ground reference requires at least two corners on each board axis"
        )
    cameras = [calibration[role] for role in ("camera_1", "camera_2")]
    rotations = [cv2.Rodrigues(np.asarray(camera["rotation"]))[0] for camera in cameras]
    shifts = [np.asarray(camera["translation"]) for camera in cameras]
    projections = [
        np.column_stack((rotation, shift))
        for rotation, shift in zip(rotations, shifts, strict=True)
    ]
    camera_centers = [
        -rotation.T @ shift for rotation, shift in zip(rotations, shifts, strict=True)
    ]
    samples = []
    for observation in observations:
        raw = [
            np.asarray(observation[role], dtype=float).reshape(-1, 2)
            for role in ("camera_1", "camera_2")
        ]
        if any(
            points.shape != (columns * rows, 2) or not np.isfinite(points).all() for points in raw
        ):
            raise CalibrationDataError("board corner coverage is incomplete")
        if any(
            np.linalg.norm(np.ptp(points, axis=0)) < settings.min_board_span_px for points in raw
        ):
            raise CalibrationDataError(
                "board image span is too small in one camera; improve visibility"
            )
        normalized = [
            cv2.undistortPoints(
                points.reshape(-1, 1, 2),
                np.asarray(camera["matrix"]),
                np.asarray(camera["distortions"]),
            ).reshape(-1, 2)
            for points, camera in zip(raw, cameras, strict=True)
        ]
        homogeneous = cv2.triangulatePoints(
            projections[0], projections[1], normalized[0].T, normalized[1].T
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            points3 = (homogeneous[:3] / homogeneous[3]).T
        if not np.isfinite(points3).all():
            raise CalibrationDataError("board triangulation is degenerate")
        for camera_index, camera in enumerate(cameras):
            if np.any((points3 @ rotations[camera_index].T + shifts[camera_index])[:, 2] <= 0):
                raise CalibrationDataError("board orientation has negative camera depth")
            projected, _ = cv2.projectPoints(
                points3,
                np.asarray(camera["rotation"]),
                shifts[camera_index],
                np.asarray(camera["matrix"]),
                np.asarray(camera["distortions"]),
            )
            error = np.linalg.norm(projected.reshape(-1, 2) - raw[camera_index], axis=1)
            if np.max(error) > settings.max_reference_error_px:
                raise CalibrationDataError(
                    f"camera_{camera_index + 1} board reprojection exceeds limits; "
                    "check corner orientation"
                )
        grid = points3.reshape(rows, columns, 3)
        lengths = np.concatenate(
            (
                np.linalg.norm(np.diff(grid, axis=1), axis=2).ravel(),
                np.linalg.norm(np.diff(grid, axis=0), axis=2).ravel(),
            )
        )
        if np.max(np.abs(lengths / square_size_m - 1)) > settings.max_length_relative_error:
            raise CalibrationDataError("measured board lengths disagree with reconstructed scale")
        origin = points3[0]
        target = points3[columns - 1] - origin
        board_side = points3[(rows - 1) * columns] - origin
        target /= np.linalg.norm(target)
        board_side -= np.dot(board_side, target) * target
        if np.linalg.norm(board_side) <= np.finfo(float).eps:
            raise CalibrationDataError("board target and side axes are degenerate")
        board_side /= np.linalg.norm(board_side)
        up = np.cross(target, board_side)
        if np.dot(up, camera_centers[0] - origin) < 0:
            up *= -1
        if any(np.dot(up, center - origin) <= 0 for center in camera_centers):
            raise CalibrationDataError("board normal orientation is ambiguous across cameras")
        plane_error = np.max(np.abs((points3 - origin) @ up))
        if plane_error > square_size_m * settings.max_length_relative_error:
            raise CalibrationDataError("board is not sufficiently planar")
        samples.append(
            {
                "capture": observation["capture"],
                "up": up,
                "target": target,
                "ball": -golfer_side * board_side,
                "origin": origin,
            }
        )
    by_capture = {
        capture: [item for item in samples if item["capture"] == capture] for capture in captures
    }
    if any(len(items) < 6 for items in by_capture.values()):
        raise CalibrationDataError(
            "each independent reference placement needs six usable synchronized frames"
        )
    fitting = by_capture[captures[0]]
    axes = {}
    for axis in ("up", "target", "ball"):
        direction = np.median([item[axis] for item in fitting], axis=0)
        direction /= np.linalg.norm(direction)
        for item in samples:
            difference = np.degrees(np.arccos(np.clip(np.dot(direction, item[axis]), -1, 1)))
            if difference > settings.max_normal_difference_deg:
                raise CalibrationDataError(
                    f"ground {axis} repeatability failed; verify marked orientation and level"
                )
        axes[axis] = direction.tolist()
    up_axis = np.asarray(axes["up"])
    target_axis = np.asarray(axes["target"])
    target_axis -= np.dot(target_axis, up_axis) * up_axis
    target_axis /= np.linalg.norm(target_axis)
    ball_axis = np.cross(up_axis, target_axis)
    if np.dot(ball_axis, axes["ball"]) < 0:
        ball_axis *= -1
    axes.update(target=target_axis.tolist(), ball=ball_axis.tolist())
    return {
        "version": 1,
        "status": "accepted",
        **axes,
        "origin": np.median([item["origin"] for item in fitting], axis=0).tolist(),
        "fit_capture": captures[0],
        "heldout_captures": captures[1:],
        "sample_counts": {capture: len(items) for capture, items in by_capture.items()},
        "square_size_m": square_size_m,
        "coordinate_frame": "camera_1",
        "units": "m",
    }


def compute_ground_reference(
    data_dir: Path,
    config: Config,
    session_ids: list[str],
    origins: dict,
    golfer_side: int,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict:
    root = resolve_state_path(config.calibration.dir)
    bundle = load_active_bundle(root)
    if bundle is None or bundle["validation"].get("status") != "accepted":
        raise CalibrationDataError(
            "accept independently validated camera geometry before capturing ground"
        )
    calibration = tomllib.loads(Path(bundle["calib_file"]).read_text())
    observations = []
    sources = {}
    for session_id in session_ids:
        if cancelled():
            raise CalibrationDataError(
                "ground reference validation cancelled; active reference unchanged"
            )
        if Path(session_id).name != session_id:
            raise CalibrationDataError("invalid reference capture identity")
        directory = Path(data_dir) / "sessions" / session_id
        marker = json.loads((directory / "calibration_shot.json").read_text())
        metadata = json.loads((directory / "metadata.json").read_text())
        compatibility = compare_signatures(
            bundle["signatures"], camera_signatures(config, metadata)
        )
        if compatibility["status"] != "compatible":
            raise CalibrationDataError(
                "ground capture camera settings are not verified compatible: "
                + "; ".join(compatibility["reasons"])
            )
        if (
            marker.get("kind") != "ground"
            or marker.get("bundle_id") != bundle["bundle_id"]
            or marker.get("level_confirmed") is not True
            or marker.get("target_confirmed") is not True
        ):
            raise CalibrationDataError(
                "reference capture lacks matching bundle, level or target evidence"
            )
        videos = [
            cv2.VideoCapture(str(directory / f"{role}.mp4")) for role in ("camera_1", "camera_2")
        ]
        try:
            counts = [int(video.get(cv2.CAP_PROP_FRAME_COUNT)) for video in videos]
            rates = [video.get(cv2.CAP_PROP_FPS) for video in videos]
            if (
                not all(video.isOpened() for video in videos)
                or len(set(counts)) != 1
                or not np.isclose(rates[0], rates[1])
            ):
                raise CalibrationDataError("ground captures need matching synchronized frame grids")
            for frame in np.linspace(0, counts[0] - 1, min(24, counts[0]), dtype=int):
                observation = {"capture": session_id, "frame": int(frame)}
                for role, video in zip(("camera_1", "camera_2"), videos, strict=True):
                    video.set(cv2.CAP_PROP_POS_FRAMES, int(frame))
                    ok, image = video.read()
                    found = (
                        detect_board_corners(
                            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY),
                            tuple(config.calibration.checkerboard_corners),
                        )
                        if ok
                        else None
                    )
                    if found is None:
                        break
                    choice = origins.get(session_id, {}).get(role)
                    if choice not in ("first", "last"):
                        raise CalibrationDataError(
                            "identify the marked board origin in both camera previews"
                        )
                    points = found.reshape(-1, 2)
                    observation[role] = points if choice == "first" else points[::-1]
                if "camera_1" in observation and "camera_2" in observation:
                    observations.append(observation)
            sources[session_id] = {
                role: fingerprint(directory / f"{role}.mp4") for role in ("camera_1", "camera_2")
            }
        finally:
            for video in videos:
                video.release()
    reference = solve_ground_reference(
        calibration,
        observations,
        tuple(config.calibration.checkerboard_corners),
        config.calibration.checkerboard_square_size_mm / 1000,
        golfer_side,
        config.calibration.validation,
    )
    reference.update(
        {
            "bundle_id": bundle["bundle_id"],
            "calibration_sha256": bundle["calibration_sha256"],
            "sources": sources,
        }
    )
    reference["observations"] = [
        {**item, "camera_1": item["camera_1"].tolist(), "camera_2": item["camera_2"].tolist()}
        for item in observations
    ]
    identity = hashlib.sha256(
        json.dumps(reference, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    path = root / "references" / f"{identity}.json"
    if not path.exists():
        atomic_json(path, reference)
    with activation_guard():
        current = load_active_bundle(root)
        if cancelled():
            raise CalibrationDataError(
                "ground reference validation cancelled; active reference unchanged"
            )
        if current is None or current["bundle_id"] != bundle["bundle_id"]:
            raise CalibrationDataError(
                "active camera bundle changed during ground validation; recapture"
            )
        atomic_json(
            root / "active.json",
            {"version": 1, "bundle_id": bundle["bundle_id"], "ground_id": identity},
        )
    return {"ground_id": identity, "bundle_id": bundle["bundle_id"], "reference": reference}
