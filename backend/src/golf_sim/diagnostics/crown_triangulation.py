"""Diagnostic-only two-view crown triangulation; never metric support."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tomllib
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

from golf_sim.config import CalibrationValidationConfig, load_config


def triangulate_crown_observations(
    first: np.ndarray,
    second: np.ndarray,
    calibration: dict,
    settings: CalibrationValidationConfig,
) -> dict:
    """Triangulate native distorted pixels with separate cheirality and pixel gates."""
    observations = [np.asarray(first, dtype=float), np.asarray(second, dtype=float)]
    if (
        observations[0].shape != observations[1].shape
        or observations[0].ndim != 2
        or observations[0].shape[1] != 2
    ):
        raise ValueError("paired observations must have identical (frames, 2) shapes")
    cameras = [calibration[role] for role in ("camera_1", "camera_2")]
    for camera in cameras:
        if camera.get("fisheye", False):
            raise ValueError("fisheye calibration is not supported by this diagnostic")
    count = len(observations[0])
    points = np.full((count, 3), np.nan)
    errors = np.full((count, 2), np.nan)
    depths = np.full((count, 2), np.nan)
    finite = np.isfinite(observations[0]).all(axis=1) & np.isfinite(observations[1]).all(axis=1)
    indices = np.flatnonzero(finite)
    if indices.size:
        projections, normalized = [], []
        for camera, pixels in zip(cameras, observations, strict=True):
            rotation = cv2.Rodrigues(np.asarray(camera["rotation"], dtype=float))[0]
            translation = np.asarray(camera["translation"], dtype=float).reshape(3, 1)
            projections.append(np.hstack((rotation, translation)))
            normalized.append(
                cv2.undistortPoints(
                    pixels[indices].reshape(-1, 1, 2),
                    np.asarray(camera["matrix"], dtype=float),
                    np.asarray(camera["distortions"], dtype=float),
                ).reshape(-1, 2)
            )
        homogeneous = cv2.triangulatePoints(
            projections[0], projections[1], normalized[0].T, normalized[1].T
        )
        with np.errstate(invalid="ignore", divide="ignore"):
            reconstructed = (homogeneous[:3] / homogeneous[3]).T
        usable = np.isfinite(reconstructed).all(axis=1)
        indices = indices[usable]
        reconstructed = reconstructed[usable]
        if indices.size:
            points[indices] = reconstructed
            for index, (camera, pixels) in enumerate(zip(cameras, observations, strict=True)):
                rotation = np.asarray(camera["rotation"], dtype=float)
                translation = np.asarray(camera["translation"], dtype=float)
                projected, _ = cv2.projectPoints(
                    reconstructed,
                    rotation,
                    translation,
                    np.asarray(camera["matrix"], dtype=float),
                    np.asarray(camera["distortions"], dtype=float),
                )
                errors[indices, index] = np.linalg.norm(
                    projected.reshape(-1, 2) - pixels[indices], axis=1
                )
                depths[indices, index] = (
                    reconstructed @ cv2.Rodrigues(rotation)[0].T + translation
                )[:, 2]
    positive = np.isfinite(depths).all(axis=1) & (depths > 0).all(axis=1)
    within = np.isfinite(errors).all(axis=1) & (errors <= settings.max_tail_error_px).all(axis=1)
    accepted = positive & within
    masked = points.copy()
    masked[~accepted] = np.nan
    return {
        "candidate_world_xyz_m": points,
        "accepted_world_xyz_m": masked,
        "errors_px": errors,
        "depths_m": depths,
        "positive_depth": positive,
        "within_reprojection_limit": within,
        "accepted": accepted,
    }


def _fingerprint(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pair_native_track_frames(first: dict, second: dict) -> list[tuple[dict | None, dict | None]]:
    """Join exact clip-time fractions without implying matching exposure times."""
    tracks = []
    for payload in (first, second):
        fps = payload["summary"]["fps"]
        if not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0:
            raise ValueError("track has invalid native fps")
        frames = {}
        previous_index = -1
        for record in payload["frames"]:
            index = record["frame_index"]
            if type(index) is not int or index < 0 or index <= previous_index:
                raise ValueError("track frame indices must be nonnegative, unique and increasing")
            if not math.isfinite(record["time_s"]) or record["time_s"] != index / fps:
                raise ValueError("track timestamp does not match its native frame identity")
            previous_index = index
            frames[Fraction(index) / Fraction(str(fps))] = record
        tracks.append(frames)
    return [
        (tracks[0].get(time), tracks[1].get(time))
        for time in sorted(set(tracks[0]) | set(tracks[1]))
    ]


def _distribution(values: np.ndarray) -> dict:
    values = values[np.isfinite(values)]
    return {
        "count": len(values),
        "median_px": float(np.median(values)) if values.size else None,
        "p95_px": float(np.percentile(values, 95)) if values.size else None,
        "max_px": float(np.max(values)) if values.size else None,
    }


def _safe(values: np.ndarray) -> list:
    return [float(value) if np.isfinite(value) else None for value in values]


def run_crown_triangulation_diagnostic(
    session_dir: Path,
    first_track: Path,
    second_track: Path,
    output_dir: Path,
    settings: CalibrationValidationConfig,
) -> dict:
    session_dir, output_dir = Path(session_dir).resolve(), Path(output_dir).resolve()
    track_paths = [Path(first_track).resolve(), Path(second_track).resolve()]
    if output_dir.is_relative_to(session_dir) or any(
        output_dir.is_relative_to(path.parent) for path in track_paths
    ):
        raise ValueError(
            "triangulation outputs must be outside source sessions and tracking directories"
        )
    metadata_path = session_dir / "metadata.json"
    calibration_path = session_dir / "pose2sim/calibration/Calib_rig.toml"
    input_paths = [metadata_path, calibration_path, *track_paths]
    inputs = {path: _fingerprint(path) for path in input_paths}
    metadata = json.loads(metadata_path.read_text())
    calibration = tomllib.loads(calibration_path.read_text())
    payloads = [json.loads(path.read_text()) for path in track_paths]
    for role, payload in zip(("camera_1", "camera_2"), payloads, strict=True):
        summary = payload["summary"]
        if summary.get(
            "tracking_policy"
        ) != "operator_seed_independent_image_motion" or not summary.get("diagnostic_only"):
            raise ValueError("operator-seeded independent-image diagnostic tracks are required")
        source_hashes = {
            Path(name).resolve(): digest for name, digest in summary["source_sha256"].items()
        }
        source = Path(summary["source_video"]).resolve()
        expected_video = session_dir / f"{role}.mp4"
        if source.stem != role or _fingerprint(expected_video) != source_hashes.get(source):
            raise ValueError("track video does not match the selected session camera")
        inputs[expected_video] = _fingerprint(expected_video)
        for path, digest in source_hashes.items():
            if _fingerprint(path) != digest:
                raise ValueError("tracking source or operator seeds changed after the experiment")
            inputs[path] = digest
        camera = metadata["cameras"][role]
        if list(calibration[role]["size"]) != [camera["width"], camera["height"]]:
            raise ValueError("saved calibration and camera dimensions are incompatible")
        if summary["fps"] != camera["fps"] or summary["frame_count"] != len(payload["frames"]):
            raise ValueError("tracking timing or frame count disagrees with saved capture")
    paired = pair_native_track_frames(*payloads)
    observations = []
    for side in (0, 1):
        observations.append(
            np.asarray(
                [
                    (
                        pair[side]["candidate_xy"]
                        if pair[side] is not None
                        and pair[side]["status"] == "image_consistent"
                        and pair[side]["candidate_xy"] is not None
                        else [np.nan, np.nan]
                    )
                    for pair in paired
                ],
                dtype=float,
            )
        )
    geometry = triangulate_crown_observations(*observations, calibration, settings)
    raw = [
        np.asarray(
            [
                (
                    pair[side]["raw_xy"]
                    if pair[side] is not None and pair[side]["raw_xy"] is not None
                    else [np.nan, np.nan]
                )
                for pair in paired
            ],
            dtype=float,
        )
        for side in (0, 1)
    ]
    raw_geometry = triangulate_crown_observations(*raw, calibration, settings)
    available = np.isfinite(observations[0]).all(axis=1) & np.isfinite(observations[1]).all(axis=1)
    raw_available = np.isfinite(raw[0]).all(axis=1) & np.isfinite(raw[1]).all(axis=1)
    common = available & raw_available

    def summary_for(result: dict, mask: np.ndarray) -> dict:
        return {
            "paired_observations": int(mask.sum()),
            "positive_depth_pairs": int((mask & result["positive_depth"]).sum()),
            "pixel_and_depth_gate_passes": int((mask & result["accepted"]).sum()),
            "camera_1_error": _distribution(result["errors_px"][mask, 0]),
            "camera_2_error": _distribution(result["errors_px"][mask, 1]),
        }

    timing = {}
    for role in ("camera_1", "camera_2"):
        camera = metadata["cameras"][role]
        receipts = camera.get("source_receipt_offsets_s", [])
        timing[role] = {
            key: camera.get(key)
            for key in (
                "fps",
                "frame_count",
                "source_frame_count",
                "source_effective_fps",
                "resampled_to_grid",
            )
        }
        timing[role]["host_receipt_timestamp_count"] = len(receipts)
        timing[role]["distinct_host_receipt_timestamps"] = len(set(receipts))
    summary = {
        "diagnostic_only": True,
        "eligible_for_metrics": False,
        "calibration_acceptance": "not_established_by_this_diagnostic",
        "exposure_synchronization_verified": False,
        "pairing_basis": "equal_native_clip_time; not verified exposure identity",
        "timing_evidence": timing,
        "calibration_sha256": inputs[calibration_path],
        "reprojection_limit_px": settings.max_tail_error_px,
        "timeline_entries": len(paired),
        "tracked": summary_for(geometry, available),
        "raw_on_same_frames": summary_for(raw_geometry, common),
        "tracked_on_same_frames": summary_for(geometry, common),
        "missing_or_unmatched_pairs": int((~available).sum()),
        "source_unchanged": True,
        "warning": (
            "Native clip-time pairing and low reprojection error do not certify exposure "
            "timing, calibration, scale or physical head excursion. "
            "No filling or interpolation is performed."
        ),
        "source_sha256": {str(path): digest for path, digest in inputs.items()},
    }
    frames = []
    for index, pair in enumerate(paired):
        record = pair[0] if pair[0] is not None else pair[1]
        frames.append(
            {
                "time_s": record["time_s"],
                "camera_1_frame": None if pair[0] is None else pair[0]["frame_index"],
                "camera_2_frame": None if pair[1] is None else pair[1]["frame_index"],
                "paired_track_available": bool(available[index]),
                "candidate_world_xyz_m": _safe(geometry["candidate_world_xyz_m"][index]),
                "gate_passed_world_xyz_m": _safe(geometry["accepted_world_xyz_m"][index]),
                "reprojection_error_px": _safe(geometry["errors_px"][index]),
                "camera_depths_m": _safe(geometry["depths_m"][index]),
                "pixel_and_depth_gates_passed": bool(geometry["accepted"][index]),
            }
        )
    if any(_fingerprint(path) != digest for path, digest in inputs.items()):
        raise RuntimeError("diagnostic input changed while triangulating")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "triangulation.json").write_text(
        json.dumps({"summary": summary, "frames": frames}, indent=2, allow_nan=False)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--first-track", type=Path, required=True)
    parser.add_argument("--second-track", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    summary = run_crown_triangulation_diagnostic(
        args.session,
        args.first_track,
        args.second_track,
        args.output,
        load_config(args.config).calibration.validation,
    )
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "source_sha256"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
