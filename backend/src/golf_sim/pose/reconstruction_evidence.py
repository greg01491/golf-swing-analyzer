"""Source-bound calibration, reference and observation evidence for exported TRCs."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import tomllib
from pathlib import Path

import cv2
import numpy as np

from golf_sim.config import Config, resolve_state_path
from golf_sim.pose.calibration_bundle import (
    atomic_json,
    camera_signatures,
    capture_signatures_from_metadata,
    compare_signatures,
    fingerprint,
    load_active_bundle,
)
from golf_sim.trc import read_trc

WORLD_TO_TRC = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
MARKER_INDICES = {
    "Nose": 0,
    "LShoulder": 5,
    "RShoulder": 6,
    "LElbow": 7,
    "RElbow": 8,
    "LWrist": 9,
    "RWrist": 10,
    "LHip": 11,
    "RHip": 12,
    "LKnee": 13,
    "RKnee": 14,
    "LAnkle": 15,
    "RAnkle": 16,
    "Head": 17,
    "Neck": 18,
    "Hip": 19,
}


def prepare_explicit_reconstruction(session_dir: Path, config: Config, bundle_id: str) -> None:
    bundle = load_active_bundle(resolve_state_path(config.calibration.dir))
    if bundle is None or bundle["bundle_id"] != bundle_id:
        raise ValueError(
            "selected camera bundle is no longer active; select compatible evidence again"
        )
    metadata_path = session_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    compatibility = compare_signatures(bundle["signatures"], camera_signatures(config, metadata))
    if compatibility["status"] != "compatible":
        raise ValueError(
            "saved capture compatibility is not established: " + "; ".join(compatibility["reasons"])
        )
    archive = session_dir / "reconstruction-history" / str(time.time_ns())
    archive.mkdir(parents=True)
    atomic_json(archive / "metadata.json", metadata)
    for path in (
        session_dir / "pose2sim" / "calibration",
        session_dir / "pose2sim" / "pose-3d",
        session_dir / "metrics.json",
    ):
        if path.exists():
            shutil.move(str(path), str(archive / path.name))
    metadata.setdefault("reconstruction_history", []).append(
        {"archive": str(archive.relative_to(session_dir)), "selected_bundle_id": bundle_id}
    )
    metadata["selected_calibration_bundle_id"] = bundle_id
    metadata.pop("reconstruction_artifacts", None)
    metadata.pop("analysis_reference", None)
    atomic_json(metadata_path, metadata)


def load_ground_evidence(root: Path, bundle: dict) -> dict | None:
    identity = bundle.get("ground_id")
    if (
        not isinstance(identity, str)
        or len(identity) != 64
        or any(character not in "0123456789abcdef" for character in identity)
    ):
        return None
    evidence = json.loads((root / "references" / f"{identity}.json").read_text())
    digest = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    if (
        digest != identity
        or evidence.get("bundle_id") != bundle["bundle_id"]
        or evidence.get("calibration_sha256") != bundle["calibration_sha256"]
        or evidence.get("status") != "accepted"
    ):
        raise ValueError("ground reference fingerprint or parent calibration mismatch")
    return evidence


def snapshot_bundle(session_dir: Path, config: Config) -> dict | None:
    bundle = load_active_bundle(resolve_state_path(config.calibration.dir))
    if bundle is None:
        return None
    metadata_path = session_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    selected = metadata.get("selected_calibration_bundle_id")
    if selected is not None and selected != bundle["bundle_id"]:
        raise ValueError("selected reconstruction bundle changed; select compatible evidence again")
    compatibility = compare_signatures(bundle["signatures"], camera_signatures(config, metadata))
    if compatibility["status"] == "incompatible":
        raise ValueError(
            "capture incompatible with camera bundle: " + "; ".join(compatibility["reasons"])
        )
    directory = session_dir / "pose2sim" / "calibration"
    ground = load_ground_evidence(resolve_state_path(config.calibration.dir), bundle)
    snapshot = {
        **bundle,
        "compatibility": compatibility,
        "ground_reference": ground,
        "capture_signatures": camera_signatures(config, metadata),
    }
    existing = directory / "snapshot.json"
    if (
        existing.exists()
        and json.loads(existing.read_text()).get("bundle_id") != bundle["bundle_id"]
    ):
        raise ValueError(
            "session already has a different camera snapshot; "
            "explicit compatible reconstruction is required"
        )
    atomic_json(existing, snapshot)
    return snapshot


def write_reconstruction_evidence(
    session_dir: Path,
    config: Config,
    snapshot: dict | None,
    trc_paths: list[Path],
    triangulation_support: list[bool] | None = None,
) -> None:
    project = session_dir / "pose2sim"
    calibration_path = project / "calibration" / "Calib_rig.toml"
    if not calibration_path.exists():
        return
    calibration = tomllib.loads(calibration_path.read_text())
    ground = None if snapshot is None else snapshot.get("ground_reference")
    for trc_path in trc_paths:
        sequence = read_trc(trc_path)
        cameras = {role: calibration[role] for role in ("camera_1", "camera_2")}
        support = {
            name: np.ones(sequence.n_frames, dtype=bool)
            for name in sequence.marker_names
            if name in MARKER_INDICES
        }
        direct_support = None
        if (
            triangulation_support is not None
            and len(triangulation_support) % len(sequence.marker_names) == 0
        ):
            direct_support = np.asarray(triangulation_support, dtype=bool).reshape(
                -1, len(sequence.marker_names)
            )
            for local_frame, timestamp in enumerate(sequence.times):
                original_frame = round(timestamp * sequence.fps)
                for name in support:
                    index = sequence.marker_names.index(name)
                    support[name][local_frame] &= (
                        original_frame < len(direct_support)
                        and direct_support[original_frame, index]
                    )
        per_camera = {}
        camera_errors = {}
        for role, camera in cameras.items():
            world = sequence.coords @ WORLD_TO_TRC
            rotation = np.asarray(camera["rotation"])
            translation = np.asarray(camera["translation"])
            matrix = np.asarray(camera["matrix"])
            distortion = np.asarray(camera["distortions"])
            projected, _ = cv2.projectPoints(
                world.reshape(-1, 3), rotation, translation, matrix, distortion
            )
            projected = projected.reshape(sequence.n_frames, len(sequence.marker_names), 2)
            depths = (world @ cv2.Rodrigues(rotation)[0].T + translation)[..., 2]
            counts = {name: 0 for name in support}
            measured_errors = []
            for local_frame, timestamp in enumerate(sequence.times):
                frame = round(timestamp * sequence.fps)
                path = project / "pose-associated" / f"{role}_json" / f"{role}_{frame:06d}.json"
                try:
                    people = json.loads(path.read_text()).get("people", [])
                    keypoints = (
                        np.asarray(people[0]["pose_keypoints_2d"]).reshape(-1, 3)
                        if len(people) == 1
                        else None
                    )
                except (OSError, ValueError, KeyError):
                    keypoints = None
                for name in support:
                    marker_index = sequence.marker_names.index(name)
                    keypoint_index = MARKER_INDICES[name]
                    valid = (
                        keypoints is not None
                        and len(keypoints) > keypoint_index
                        and np.isfinite(keypoints[keypoint_index]).all()
                        and keypoints[keypoint_index, 2] >= 0.3
                    )
                    if valid:
                        error = np.linalg.norm(
                            projected[local_frame, marker_index] - keypoints[keypoint_index, :2]
                        )
                        if np.isfinite(error):
                            measured_errors.append(float(error))
                        valid = (
                            np.isfinite(error)
                            and error <= config.calibration.validation.max_tail_error_px
                            and depths[local_frame, marker_index] > 0
                        )
                    support[name][local_frame] &= valid
                    counts[name] += int(valid)
            per_camera[role] = {name: count / sequence.n_frames for name, count in counts.items()}
            camera_errors[role] = {
                "median_px": float(np.median(measured_errors)) if measured_errors else None,
                "p95_px": float(np.percentile(measured_errors, 95)) if measured_errors else None,
            }
        regions = {
            "shoulders": ("LShoulder", "RShoulder"),
            "pelvis": ("Hip", "LHip", "RHip"),
            "head": ("Head", "Neck"),
            "legs": ("LKnee", "RKnee", "LAnkle", "RAnkle"),
        }
        region_coverage = {
            name: min(
                float(support[marker].mean()) if marker in support else 0.0 for marker in markers
            )
            for name, markers in regions.items()
        }
        reasons = [
            f"{name} supported coverage is {coverage:.0%}"
            for name, coverage in region_coverage.items()
            if coverage < config.calibration.validation.min_coverage
        ]
        artifact = {
            "version": 1,
            "source_trc_sha256": fingerprint(trc_path),
            "calibration_sha256": fingerprint(calibration_path),
            "world_to_trc": WORLD_TO_TRC.tolist(),
            "units": "m",
            "calibration_status": (
                "legacy-unverified" if snapshot is None else snapshot["validation"]["status"]
            ),
            "bundle_id": None if snapshot is None else snapshot["bundle_id"],
            "compatibility": None if snapshot is None else snapshot["compatibility"],
            "marker_support": {name: values.tolist() for name, values in support.items()},
            "camera_coverage": per_camera,
            "session_validation": {
                "status": "failed" if reasons else "accepted",
                "reasons": reasons,
                "regions": region_coverage,
                "camera_errors": camera_errors,
            },
            "observation_provenance": (
                "pre_fill_triangulation" if direct_support is not None else "unavailable"
            ),
            "pre_fill_support": None if direct_support is None else direct_support.tolist(),
        }
        if (
            ground is not None
            and snapshot["compatibility"]["status"] == "compatible"
            and direct_support is not None
        ):
            artifact["analysis_reference"] = {
                "source": "calibrated_ground",
                "validated": True,
                "source_trc_sha256": fingerprint(trc_path),
                "bundle_id": snapshot["bundle_id"],
                "ground_id": snapshot["ground_id"],
                **{
                    axis: (WORLD_TO_TRC @ np.asarray(ground[axis])).tolist()
                    for axis in ("up", "target", "ball")
                },
            }
        evidence_path = trc_path.with_suffix(".evidence.json")
        atomic_json(evidence_path, artifact)
        metadata_path = session_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
        artifacts = metadata.setdefault("reconstruction_artifacts", {})
        artifacts[trc_path.name] = {
            "source_trc_sha256": fingerprint(trc_path),
            "evidence_sha256": fingerprint(evidence_path),
        }
        atomic_json(metadata_path, metadata)


def review_camera_tolerances(trc_path: Path, config: Config, issues: list[dict]) -> dict:
    """Measure requested observations against the exact saved reconstruction calibration."""
    artifact = verified_artifact_evidence(trc_path)
    if artifact is None:
        return {
            "available": False,
            "reason": "Bound reconstruction evidence unavailable",
            "failures": {},
        }
    sequence = read_trc(trc_path)
    project = trc_path.parent.parent
    calibration = tomllib.loads((project / "calibration" / "Calib_rig.toml").read_text())
    failures = {}
    world = sequence.coords @ WORLD_TO_TRC
    for role in ("camera_1", "camera_2"):
        requested = {
            (issue["marker"], frame, issue["fps"])
            for issue in issues
            if issue["camera"] == role and issue["marker"] in MARKER_INDICES
            for frame in issue["frame_indices"]
        }
        if not requested:
            continue
        camera = calibration[role]
        rotation = np.asarray(camera["rotation"], dtype=float)
        translation = np.asarray(camera["translation"], dtype=float)
        projected, _ = cv2.projectPoints(
            world.reshape(-1, 3),
            rotation,
            translation,
            np.asarray(camera["matrix"], dtype=float),
            np.asarray(camera["distortions"], dtype=float),
        )
        projected = projected.reshape(sequence.n_frames, len(sequence.marker_names), 2)
        depths = (world @ cv2.Rodrigues(rotation)[0].T + translation)[..., 2]
        associated = project / "pose-associated" / f"{role}_json"
        directory = associated if associated.is_dir() else project / "pose" / f"{role}_json"
        frames = {}
        for marker, frame, fps in sorted(requested):
            if marker not in sequence.marker_names:
                continue
            if frame not in frames:
                try:
                    people = json.loads((directory / f"{role}_{frame:06d}.json").read_text()).get(
                        "people", []
                    )
                    frames[frame] = (
                        np.asarray(people[0]["pose_keypoints_2d"], dtype=float).reshape(-1, 3)
                        if len(people) == 1
                        else None
                    )
                except (OSError, ValueError, KeyError, TypeError):
                    frames[frame] = None
            points = frames[frame]
            if points is None or len(points) <= MARKER_INDICES[marker]:
                continue
            point = points[MARKER_INDICES[marker]]
            if not np.isfinite(point).all():
                continue
            if point[2] < 0.3:
                failures[f"{role}/{marker}/{frame}"] = {
                    "reason": "2D confidence below observation threshold",
                    "value": float(point[2]),
                    "threshold": 0.3,
                    "unit": "score",
                }
                continue
            local = int(np.argmin(np.abs(sequence.times - frame / fps)))
            index = sequence.marker_names.index(marker)
            error = float(np.linalg.norm(projected[local, index] - point[:2]))
            limit = config.calibration.validation.max_tail_error_px
            if np.isfinite(error) and error > limit:
                failures[f"{role}/{marker}/{frame}"] = {
                    "reason": "Reprojection error exceeds tolerance",
                    "value": error,
                    "threshold": limit,
                    "unit": "px",
                }
            elif np.isfinite(depths[local, index]) and depths[local, index] <= 0:
                failures[f"{role}/{marker}/{frame}"] = {
                    "reason": "Point is behind the camera",
                    "value": float(depths[local, index]),
                    "threshold": 0,
                    "unit": "m",
                }
    return {"available": True, "reason": None, "failures": failures}


def verified_artifact_evidence(trc_path: Path) -> dict | None:
    path = trc_path.with_suffix(".evidence.json")
    if not path.exists():
        return None
    evidence = json.loads(path.read_text())
    metadata = json.loads((trc_path.parent.parent.parent / "metadata.json").read_text())
    binding = metadata.get("reconstruction_artifacts", {}).get(trc_path.name, {})
    if binding.get("source_trc_sha256") != fingerprint(trc_path) or binding.get(
        "evidence_sha256"
    ) != fingerprint(path):
        raise ValueError("reconstruction evidence digest does not match session metadata")
    calibration = trc_path.parent.parent / "calibration" / "Calib_rig.toml"
    if (
        evidence.get("version") != 1
        or evidence.get("source_trc_sha256") != fingerprint(trc_path)
        or evidence.get("calibration_sha256") != fingerprint(calibration)
    ):
        raise ValueError("reconstruction evidence no longer matches its coordinate artifact")
    reference = evidence.get("analysis_reference")
    if reference is not None:
        snapshot = json.loads((calibration.parent / "snapshot.json").read_text())
        manifest = {
            key: snapshot[key]
            for key in ("version", "calibration_sha256", "validation", "signatures")
        }
        digest = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        ground = snapshot.get("ground_reference")
        ground_id = hashlib.sha256(
            json.dumps(ground, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        if (
            digest != snapshot.get("bundle_id")
            or digest != reference.get("bundle_id")
            or snapshot["validation"].get("status") != "accepted"
            or ground is None
            or ground.get("status") != "accepted"
            or ground_id != snapshot.get("ground_id")
            or ground_id != reference.get("ground_id")
            or ground.get("bundle_id") != digest
            or ground.get("calibration_sha256") != fingerprint(calibration)
        ):
            raise ValueError("reference calibration/ground chain is not independently accepted")
        current_signatures = capture_signatures_from_metadata(metadata)
        if (
            current_signatures != snapshot.get("capture_signatures")
            or compare_signatures(snapshot["signatures"], current_signatures)["status"]
            != "compatible"
        ):
            raise ValueError("reference capture signatures no longer match the session")
        for axis in ("up", "target", "ball"):
            expected = WORLD_TO_TRC @ np.asarray(ground[axis])
            if not np.allclose(expected, reference.get(axis)):
                raise ValueError("reference axes do not match the measured TRC transform")
    return evidence
