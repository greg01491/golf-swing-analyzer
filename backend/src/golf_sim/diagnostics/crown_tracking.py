"""Image-supported Head-point experiment; never a source of metric support."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from golf_sim.config import CrownTrackingDiagnosticConfig, load_config


class OperatorCrownSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    camera: Literal["camera_1", "camera_2"]
    video_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frame_index: int = Field(ge=0, strict=True)
    native_width: int = Field(gt=0, strict=True)
    native_height: int = Field(gt=0, strict=True)
    x: FiniteFloat = Field(ge=0)
    y: FiniteFloat = Field(ge=0)
    confirmed_visible: Literal[True]
    origin: Literal["operator_click"] = "operator_click"


class OperatorCrownSeeds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    annotations: list[OperatorCrownSeed] = Field(default_factory=list)


class HeadPointTracker:
    """Follow image motion from a detector or operator seed without certifying anatomy."""

    def __init__(
        self, settings: CrownTrackingDiagnosticConfig, *, operator_seeded: bool = False
    ) -> None:
        self.settings = settings
        self.operator_seeded = operator_seeded
        self.previous_gray: np.ndarray | None = None
        self.previous_point: np.ndarray | None = None
        self.previous_observation: np.ndarray | None = None
        self.previous_motion = np.zeros(2)

    def update(
        self,
        image: np.ndarray,
        observation: np.ndarray | None,
        *,
        seed_xy: np.ndarray | None = None,
    ) -> dict:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        result = {
            "candidate_xy": None,
            "status": "detector_unavailable",
            "detector_distance_px": None,
            "detector_motion_disagreement_px": None,
            "flow_inlier_fraction": None,
        }
        point = None if observation is None else np.asarray(observation, dtype=float)
        height, width = gray.shape
        valid = (
            point is not None
            and point.shape == (3,)
            and np.isfinite(point).all()
            and point[2] >= self.settings.min_confidence
            and 0 <= point[0] < width
            and 0 <= point[1] < height
        )
        if not valid and not self.operator_seeded:
            self.previous_point = None
            self.previous_observation = None
            self.previous_gray = gray
            return result
        if seed_xy is not None:
            seed = np.asarray(seed_xy, dtype=float)
            if (
                not self.operator_seeded
                or seed.shape != (2,)
                or not np.isfinite(seed).all()
                or not (0 <= seed[0] < width and 0 <= seed[1] < height)
            ):
                raise ValueError(
                    "operator seed must be a finite native-image point in operator mode"
                )
            self.previous_point = seed.copy()
            self.previous_observation = point[:2].copy() if valid else None
            self.previous_motion = np.zeros(2)
            self.previous_gray = gray
            return {**result, "status": "operator_seed_recorded"}
        if (
            self.previous_point is None
            or self.previous_gray is None
            or self.previous_gray.shape != gray.shape
        ):
            if self.operator_seeded:
                self.previous_gray = gray
                self.previous_point = None
                self.previous_observation = None
                return {**result, "status": "awaiting_operator_seed"}
            self.previous_point = point[:2].copy()
            self.previous_observation = point[:2].copy()
            self.previous_gray = gray
            return {**result, "status": "seed_unverified"}

        previous_point = self.previous_point.copy()
        detector_motion = (
            point[:2] - self.previous_observation
            if valid and self.previous_observation is not None
            else None
        )
        hint = previous_point + self.previous_motion if self.operator_seeded else point[:2]
        prediction, reason, fraction = self._motion(gray, hint)
        self.previous_gray = gray
        self.previous_point = None
        self.previous_observation = None
        result["status"] = reason
        result["flow_inlier_fraction"] = fraction
        if prediction is None:
            return result
        distance = float(np.linalg.norm(prediction - point[:2])) if valid else None
        motion_disagreement = (
            float(np.linalg.norm(prediction - previous_point - detector_motion))
            if detector_motion is not None
            else None
        )
        result["detector_distance_px"] = distance
        result["detector_motion_disagreement_px"] = motion_disagreement
        if not (0 <= prediction[0] < width and 0 <= prediction[1] < height):
            return {**result, "status": "tracked_point_outside_image"}
        if not self.operator_seeded and distance > self.settings.max_detector_disagreement_px:
            return {**result, "status": "detector_disagreement"}
        self.previous_point = prediction
        self.previous_observation = point[:2].copy() if valid else None
        self.previous_motion = prediction - previous_point
        return {**result, "candidate_xy": prediction.tolist(), "status": "image_consistent"}

    def _motion(
        self, gray: np.ndarray, detected_point: np.ndarray
    ) -> tuple[np.ndarray | None, str, float | None]:
        settings = self.settings
        mask = np.zeros_like(self.previous_gray)
        center = tuple(np.round(self.previous_point).astype(int))
        cv2.circle(mask, center, settings.feature_radius_px, 255, -1)
        features = cv2.goodFeaturesToTrack(
            self.previous_gray,
            maxCorners=settings.max_features,
            qualityLevel=settings.feature_quality,
            minDistance=settings.min_feature_distance_px,
            mask=mask,
        )
        if features is None or len(features) < settings.min_features:
            return None, "insufficient_image_features", None
        options = {
            "winSize": (settings.lk_window_px, settings.lk_window_px),
            "maxLevel": min(
                settings.lk_max_level,
                max(0, int(np.floor(np.log2(min(gray.shape) / settings.lk_window_px))) - 1),
            ),
            "flags": cv2.OPTFLOW_USE_INITIAL_FLOW,
        }
        initial = features + (detected_point - self.previous_point).astype(np.float32)
        forward, forward_status, _ = cv2.calcOpticalFlowPyrLK(
            self.previous_gray, gray, features, initial, **options
        )
        if forward is None:
            return None, "forward_flow_failed", None
        backward, backward_status, _ = cv2.calcOpticalFlowPyrLK(
            gray, self.previous_gray, forward, features.copy(), **options
        )
        if backward is None:
            return None, "backward_flow_failed", None
        valid = forward_status.ravel().astype(bool) & backward_status.ravel().astype(bool)
        valid &= np.isfinite(forward).all(axis=(1, 2)) & np.isfinite(backward).all(axis=(1, 2))
        valid &= (
            np.linalg.norm(backward - features, axis=2).ravel()
            <= settings.max_forward_backward_error_px
        )
        if valid.sum() < settings.min_features:
            return None, "forward_backward_inconsistent", None
        transform, inliers = cv2.estimateAffinePartial2D(
            features[valid],
            forward[valid],
            method=cv2.RANSAC,
            ransacReprojThreshold=settings.ransac_reprojection_px,
        )
        if transform is None or inliers is None or not np.isfinite(transform).all():
            return None, "image_transform_unavailable", None
        fraction = float(inliers.mean())
        if int(inliers.sum()) < settings.min_features or fraction < settings.min_inlier_fraction:
            return None, "insufficient_motion_inliers", fraction
        prediction = transform @ np.append(self.previous_point, 1.0)
        return prediction, "image_consistent", fraction


def _fingerprint(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _observation(path: Path) -> np.ndarray | None:
    try:
        people = json.loads(path.read_text()).get("people", [])
        if len(people) != 1:
            return None
        points = np.asarray(people[0]["pose_keypoints_2d"], dtype=float).reshape(-1, 3)
        return points[17] if len(points) >= 26 else None
    except (OSError, KeyError, ValueError, TypeError):
        return None


def _trajectory_summary(points: list) -> dict:
    values = np.asarray([point if point is not None else [np.nan, np.nan] for point in points])
    valid = np.isfinite(values).all(axis=1)
    steps = np.linalg.norm(np.diff(values, axis=0), axis=1)
    steps = steps[valid[:-1] & valid[1:]]
    return {
        "frames": int(valid.sum()),
        "comparable_steps": len(steps),
        "step_median_px": float(np.median(steps)) if steps.size else None,
        "step_p95_px": float(np.percentile(steps, 95)) if steps.size else None,
        "step_max_px": float(np.max(steps)) if steps.size else None,
        "extent_xy_px": np.ptp(values[valid], axis=0).tolist() if valid.any() else None,
    }


def _load_operator_seeds(
    path: Path, video: Path, digest: str, width: int, height: int, count: int
) -> dict[int, list[float]]:
    saved = OperatorCrownSeeds.model_validate_json(path.read_text())
    seeds = {}
    for annotation in saved.annotations:
        if annotation.video_sha256 != digest or annotation.camera != video.stem:
            continue
        if (
            annotation.native_width != width
            or annotation.native_height != height
            or annotation.frame_index >= count
            or annotation.x >= width
            or annotation.y >= height
            or annotation.frame_index in seeds
        ):
            raise ValueError("operator seed has invalid frame, image dimensions or coordinates")
        seeds[annotation.frame_index] = [annotation.x, annotation.y]
    if not seeds:
        raise ValueError("no operator seed matches this exact video and camera")
    return seeds


def run_head_tracking_diagnostic(
    video_path: Path,
    pose_directory: Path,
    output_directory: Path,
    settings: CrownTrackingDiagnosticConfig,
    *,
    write_video: bool = False,
    seed_file: Path | None = None,
) -> dict:
    """Write a separate comparison, never replacement poses or metric evidence."""
    video_path = Path(video_path).resolve()
    pose_directory = Path(pose_directory).resolve()
    output_directory = Path(output_directory).resolve()
    if output_directory.is_relative_to(video_path.parent) or output_directory.is_relative_to(
        pose_directory
    ):
        raise ValueError("diagnostic output must be outside the source session and pose directory")
    pose_inputs = set(pose_directory.glob("*.json"))
    inputs = {path: _fingerprint(path) for path in [video_path, *sorted(pose_inputs)]}
    if seed_file is not None:
        seed_file = Path(seed_file).resolve()
        inputs[seed_file] = _fingerprint(seed_file)
    capture = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
    if not capture.isOpened():
        capture.release()
        raise ValueError("source video cannot be opened")
    writer = None
    records = []
    try:
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        if count <= 0 or not np.isfinite(fps) or fps <= 0:
            raise ValueError("source video has no valid native frame timing")
        seeds = (
            {}
            if seed_file is None
            else _load_operator_seeds(
                seed_file,
                video_path,
                inputs[video_path],
                int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                count,
            )
        )
        output_directory.mkdir(parents=True, exist_ok=False)
        tracker = HeadPointTracker(settings, operator_seeded=seed_file is not None)
        while True:
            ok, image = capture.read()
            if not ok:
                break
            index = len(records)
            observation = _observation(pose_directory / f"{video_path.stem}_{index:06d}.json")
            seed = seeds.get(index)
            result = tracker.update(image, observation, seed_xy=seed)
            height, width = image.shape[:2]
            valid = (
                observation is not None
                and np.isfinite(observation).all()
                and observation[2] >= settings.min_confidence
                and 0 <= observation[0] < width
                and 0 <= observation[1] < height
            )
            raw = observation[:2].tolist() if valid else None
            record = {
                "frame_index": index,
                "time_s": index / fps,
                "raw_xy": raw,
                "operator_seed_xy": seed,
                **result,
            }
            records.append(record)
            if write_video:
                if writer is None:
                    writer = cv2.VideoWriter(
                        str(output_directory / "comparison.mp4"),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        fps,
                        (width, height),
                    )
                    if not writer.isOpened():
                        raise RuntimeError("diagnostic comparison video could not be created")
                for point, color in ((raw, (0, 165, 255)), (result["candidate_xy"], (0, 220, 0))):
                    if point is not None:
                        cv2.circle(image, tuple(np.round(point).astype(int)), 5, color, 2)
                cv2.putText(
                    image,
                    f'{index}: {result["status"]}',
                    (12, 24),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                )
                cv2.putText(
                    image,
                    "orange: detector / green: image-tracked; crown unverified",
                    (12, 48),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (255, 255, 255),
                    1,
                )
                writer.write(image)
        if len(records) != count:
            raise ValueError(f"incomplete video decode: {len(records)}/{count} frames")
    finally:
        capture.release()
        if writer is not None:
            writer.release()
    if set(pose_directory.glob("*.json")) != pose_inputs:
        raise RuntimeError("source pose file set changed during the diagnostic")
    if any(_fingerprint(path) != digest for path, digest in inputs.items()):
        raise RuntimeError("source video or pose observations changed during the diagnostic")
    summary = {
        "diagnostic_only": True,
        "eligible_for_metrics": False,
        "anatomical_crown_verified": False,
        "seed_source": (
            "operator-confirmed visible image point; trajectory anatomically unverified"
            if seed_file is not None
            else "unverified HALPE_26 Head detector observation"
        ),
        "operator_seed_file": str(seed_file) if seed_file is not None else None,
        "operator_seed_frames": sorted(seeds),
        "tracking_policy": (
            "operator_seed_independent_image_motion"
            if seed_file is not None
            else "detector_seed_with_detector_disagreement_guard"
        ),
        "source_video": str(video_path),
        "source_pose_directory": str(pose_directory),
        "source_sha256": {str(path): digest for path, digest in inputs.items()},
        "source_unchanged": True,
        "frame_count": len(records),
        "fps": fps,
        "settings": settings.model_dump(),
        "status_counts": dict(Counter(record["status"] for record in records)),
        "image_supported_fraction": sum(record["candidate_xy"] is not None for record in records)
        / len(records),
        "raw_all": _trajectory_summary([record["raw_xy"] for record in records]),
        "raw_on_supported_frames": _trajectory_summary(
            [record["raw_xy"] if record["candidate_xy"] is not None else None for record in records]
        ),
        "candidate": _trajectory_summary([record["candidate_xy"] for record in records]),
        "warning": (
            "Image consistency is not crown ground truth; lower jitter alone does not "
            "certify accuracy or real-motion retention."
        ),
    }
    (output_directory / "comparison.json").write_text(
        json.dumps({"summary": summary, "frames": records}, indent=2, allow_nan=False)
    )
    if write_video:
        from golf_sim.capture.transcode import ensure_h264

        ensure_h264(output_directory / "comparison.mp4")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--poses", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--write-video", action="store_true")
    parser.add_argument("--seeds", type=Path)
    args = parser.parse_args()
    cv2.setNumThreads(1)
    settings = load_config(args.config).pose.crown_tracking_diagnostic
    summary = run_head_tracking_diagnostic(
        args.video,
        args.poses,
        args.output,
        settings,
        write_video=args.write_video,
        seed_file=args.seeds,
    )
    print(
        json.dumps(
            {key: value for key, value in summary.items() if key != "source_sha256"},
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
