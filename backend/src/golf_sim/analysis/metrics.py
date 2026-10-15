"""Versioned swing measurements with explicit geometry and evidence requirements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from golf_sim.analysis.frame_of_reference import AnalysisReference, infer_reference
from golf_sim.analysis.phases import PhaseDetectionError, SwingPhases, detect_phases
from golf_sim.config import Club, MetricsConfig
from golf_sim.trc import LandmarkSequence


@dataclass
class MetricResult:
    name: str
    value: float
    unit: str
    in_range: bool | None  # None = no reference range configured
    range_min: float | None
    range_max: float | None
    status: Literal["valid", "estimated", "unavailable"] = "valid"
    definition_id: str = ""
    reasons: list[str] = field(default_factory=list)


@dataclass
class MetricsReport:
    phases: SwingPhases
    metrics: list[MetricResult]
    reference_frame: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "analysis_version": 2,
            "reference_frame": self.reference_frame,
            "phases": {
                "address_frame": self.phases.address_frame,
                "top_frame": self.phases.top_frame,
                "impact_frame": self.phases.impact_frame,
                "status": self.phases.status,
            },
            "metrics": [
                {
                    "name": m.name,
                    "value": round(m.value, 2) if np.isfinite(m.value) else None,
                    "unit": m.unit,
                    "in_range": m.in_range if m.status == "valid" else None,
                    "definition_id": m.definition_id or f"{m.name}:2",
                    "status": m.status,
                    "reasons": m.reasons,
                    "range": (
                        None if m.range_min is None else {"min": m.range_min, "max": m.range_max}
                    ),
                }
                for m in self.metrics
            ],
        }


def _peak_magnitude(series: np.ndarray) -> float:
    finite = series[np.isfinite(series)]
    return float(np.max(np.abs(finite))) if finite.size else float("nan")


def _supported_turn(
    seq: LandmarkSequence,
    left: str,
    right: str,
    address: int,
    config: MetricsConfig,
    reference: AnalysisReference,
    marker_support: dict[str, np.ndarray] | None = None,
) -> np.ndarray:
    angles = np.full(seq.n_frames, np.nan)
    if reference.up is None or not all(seq.has_marker(name) for name in (left, right)):
        return angles
    line = seq.marker(right) - seq.marker(left)
    body_lengths = np.linalg.norm(line, axis=1)
    finite_lengths = body_lengths[np.isfinite(body_lengths)]
    median_length = np.median(finite_lengths) if finite_lengths.size else float("nan")
    length_valid = body_lengths <= median_length * config.max_limb_length_ratio
    length_valid &= body_lengths >= median_length / config.max_limb_length_ratio
    line = line - (line @ reference.up)[:, None] * reference.up
    lengths = np.linalg.norm(line, axis=1)
    supported = np.isfinite(line).all(axis=1) & (lengths >= config.min_projected_width_m)
    supported &= length_valid
    for marker_name in (left, right):
        evidence = None if marker_support is None else marker_support.get(marker_name)
        if evidence is not None:
            if np.asarray(evidence).shape != (seq.n_frames,):
                return angles
            supported &= np.asarray(evidence, dtype=bool)
    quiet = supported & (seq.times <= seq.times[address])
    quiet &= seq.times >= seq.times[address] - config.address_window_s
    if not quiet.any():
        return angles
    origin = np.median(line[quiet], axis=0)
    if np.linalg.norm(origin) < config.min_projected_width_m:
        return angles
    origin /= np.linalg.norm(origin)
    angles[supported] = np.degrees(
        np.arctan2(np.cross(origin, line[supported]) @ reference.up, line[supported] @ origin)
    )
    half = max(1, round(config.turn_filter_window_s * seq.fps / 2))
    filtered = np.full_like(angles, np.nan)
    for index, angle in enumerate(angles):
        if not np.isfinite(angle):
            continue
        segment = angles[max(0, index - half) : index + half + 1]
        finite = segment[np.isfinite(segment)]
        if not finite.size:
            continue
        distances = np.abs((finite[:, None] - finite[None, :] + 180) % 360 - 180)
        center = finite[int(np.argmin(distances.sum(axis=1)))]
        median = center + float(np.median((finite - center + 180) % 360 - 180))
        correction = float((median - angle + 180) % 360 - 180)
        if abs(correction) <= config.turn_outlier_deg:
            filtered[index] = (angle + correction + 180) % 360 - 180
    return filtered


def _joint_angle_series(seq: LandmarkSequence, a: str, b: str, c: str) -> np.ndarray:
    """Per-frame included angle (degrees) at joint ``b`` of the a-b-c chain."""
    va = seq.marker(a) - seq.marker(b)
    vc = seq.marker(c) - seq.marker(b)
    dots = np.sum(va * vc, axis=1)
    norms = np.linalg.norm(va, axis=1) * np.linalg.norm(vc, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos_angle = np.clip(dots / norms, -1.0, 1.0)
    return np.degrees(np.arccos(cos_angle))


def compute_metrics(
    seq: LandmarkSequence,
    metrics_config: MetricsConfig,
    phases: SwingPhases | None = None,
    handedness: str = "right",
    club: Club | None = None,
    reference: AnalysisReference | None = None,
    marker_support: dict[str, np.ndarray] | None = None,
) -> MetricsReport:
    reference = reference if reference is not None else infer_reference(seq, handedness)
    if phases is None:
        phases = detect_phases(seq, reference=reference)
    address, top, impact = phases.address_frame, phases.top_frame, phases.impact_frame
    if not 0 <= address < top < impact < seq.n_frames:
        raise PhaseDetectionError("analysis requires ordered address, top and impact frames")
    timestamps_valid = bool(np.isfinite(seq.times).all() and (np.diff(seq.times) > 0).all())
    backswing = slice(address, top + 1)
    active = np.arange(address, impact + 1)
    reference_ranges = metrics_config.ranges_for_club(club)
    results: list[MetricResult] = []

    def marker(name: str) -> np.ndarray:
        if seq.has_marker(name):
            return seq.marker(name)
        return np.full((seq.n_frames, 3), np.nan)

    pelvis_height = np.linalg.norm(
        marker("Hip") - (marker("LAnkle") + marker("RAnkle")) / 2, axis=1
    )
    finite_height = pelvis_height[np.isfinite(pelvis_height)]
    scale_valid = not finite_height.size or (
        metrics_config.min_pelvis_height_m
        <= np.median(finite_height)
        <= metrics_config.max_pelvis_height_m
    )

    def add(
        name: str,
        value: float,
        unit: str,
        markers: tuple[str, ...] = (),
        frames: np.ndarray | None = None,
        directions: tuple[str, ...] = (),
        supported: np.ndarray | None = None,
    ) -> None:
        status = "valid"
        reasons: list[str] = []
        required = active if frames is None else frames
        coverage = np.ones(len(required), dtype=bool)
        for marker_name in markers:
            coverage &= np.isfinite(marker(marker_name)[required]).all(axis=1)
            evidence = None if marker_support is None else marker_support.get(marker_name)
            if evidence is None:
                reasons.append(
                    f"unverified_marker: {marker_name} has no independent observation support"
                )
            elif np.asarray(evidence).shape != (seq.n_frames,):
                coverage[:] = False
                reasons.append(f"invalid_support: {marker_name}")
            else:
                coverage &= np.asarray(evidence, dtype=bool)[required]
        if supported is not None:
            coverage &= supported[required]
        if not coverage.size or coverage.mean() < metrics_config.min_supported_fraction:
            value = float("nan")
            reasons.append("insufficient_coverage: required observations are missing or invalid")
        for direction in directions:
            if getattr(reference, direction) is None:
                value = float("nan")
                reasons.append(f"missing_reference: {direction} direction is unavailable")
        if directions and reference.status != "valid":
            reasons.extend(
                reference.reasons or ["estimated_reference: physical ground is unverified"]
            )
            if reference.status == "unavailable":
                value = float("nan")
        if getattr(phases, "status", "valid") != "valid":
            reasons.append("estimated_phases: phase anchors are not independently verified")
        if not timestamps_valid:
            value = float("nan")
            reasons.append("invalid_timestamps: finite increasing times are required")
        if not scale_valid:
            value = float("nan")
            reasons.append("invalid_scale: reconstructed pelvis height is implausible")
        if not np.isfinite(value):
            status = "unavailable"
            reasons.append("unsupported_geometry: required geometry is missing or degenerate")
        elif reasons:
            status = "estimated"
        ref = reference_ranges.get(name) if metrics_config.range_definition_version == 2 else None
        if name in reference_ranges and ref is None:
            reasons.append("incompatible_target: target definition version requires review")
        lo, hi = (None, None) if ref is None else (ref.min, ref.max)
        in_range = bool(lo <= value <= hi) if ref is not None and status == "valid" else None
        results.append(
            MetricResult(
                name=name,
                value=float(value),
                unit=unit,
                in_range=in_range,
                range_min=lo,
                range_max=hi,
                status=status,
                definition_id=f"{name}:2",
                reasons=list(dict.fromkeys(reasons)),
            )
        )

    up = reference.up if reference.up is not None else np.full(3, np.nan)
    ball = reference.ball if reference.ball is not None else np.full(3, np.nan)
    target = reference.target if reference.target is not None else np.full(3, np.nan)
    shoulder_turn = _supported_turn(
        seq, "LShoulder", "RShoulder", address, metrics_config, reference, marker_support
    )
    hip_turn = _supported_turn(
        seq, "LHip", "RHip", address, metrics_config, reference, marker_support
    )
    shoulder_markers = ("LShoulder", "RShoulder")
    hip_markers = ("LHip", "RHip")
    turn_frames = np.arange(address, top + 1)
    add(
        "shoulder_turn_deg",
        _peak_magnitude(shoulder_turn[backswing]),
        "deg",
        shoulder_markers,
        turn_frames,
        ("up",),
        np.isfinite(shoulder_turn),
    )
    add(
        "hip_turn_deg",
        _peak_magnitude(hip_turn[backswing]),
        "deg",
        hip_markers,
        turn_frames,
        ("up",),
        np.isfinite(hip_turn),
    )
    separation = (shoulder_turn - hip_turn + 180) % 360 - 180
    add(
        "x_factor_deg",
        _peak_magnitude(separation[backswing]),
        "deg",
        shoulder_markers + hip_markers,
        turn_frames,
        ("up",),
        np.isfinite(separation),
    )
    spine = marker("Neck") - marker("Hip")
    forward = np.degrees(np.arctan2(spine @ ball, spine @ up))
    spine_valid = np.linalg.norm(spine, axis=1) > metrics_config.min_projected_width_m
    add(
        "spine_tilt_deg",
        forward[address],
        "deg",
        ("Hip", "Neck"),
        np.array([address]),
        ("up", "ball"),
        spine_valid,
    )
    back_time = seq.times[top] - seq.times[address]
    down_time = seq.times[impact] - seq.times[top]
    add(
        "tempo_ratio",
        back_time / down_time if down_time > 0 else float("nan"),
        "ratio",
        ("LWrist", "RWrist"),
    )
    stance = marker("LAnkle")[address] - marker("RAnkle")[address]
    stance -= np.dot(stance, up) * up
    width = np.linalg.norm(stance)
    stance_direction = (
        stance / width if width >= metrics_config.min_projected_width_m else np.full(3, np.nan)
    )
    hip = marker("Hip")
    for name, frame in (("hip_sway_top_pct", top), ("hip_sway_impact_pct", impact)):
        sway = (
            abs((hip[frame] - hip[address]) @ stance_direction) / width * 100
            if width > 0
            else float("nan")
        )
        add(
            name,
            sway,
            "% stance width",
            ("Hip", "LAnkle", "RAnkle"),
            np.array([address, frame]),
            ("up",),
        )
    opening_sign = np.sign(np.dot(np.cross(ball, target), up))
    add(
        "hip_rotation_impact_deg",
        hip_turn[impact] * opening_sign,
        "deg",
        hip_markers,
        np.array([address, impact]),
        ("up", "target", "ball"),
        np.isfinite(hip_turn),
    )
    add("backswing_time_s", back_time, "s", ("LWrist", "RWrist"), np.arange(address, top + 1))
    add("downswing_time_s", down_time, "s", ("LWrist", "RWrist"), np.arange(top, impact + 1))
    shoulder_line = marker("LShoulder") - marker("RShoulder")
    shoulder_line *= 1 if handedness == "right" else -1
    vertical = shoulder_line @ up
    horizontal = shoulder_line - vertical[:, None] * up
    tilt = np.degrees(np.arctan2(vertical, np.linalg.norm(horizontal, axis=1)))
    add(
        "shoulder_tilt_impact_deg",
        tilt[impact],
        "deg",
        shoulder_markers,
        np.array([impact]),
        ("up",),
        np.linalg.norm(shoulder_line, axis=1) >= metrics_config.min_projected_width_m,
    )
    add(
        "spine_angle_change_deg",
        abs(forward[impact] - forward[address]),
        "deg",
        ("Hip", "Neck"),
        np.array([address, impact]),
        ("up", "ball"),
        spine_valid,
    )
    head = marker("Head")
    head_evidence = None if marker_support is None else marker_support.get("Head")
    if head_evidence is not None and np.asarray(head_evidence).shape == (seq.n_frames,):
        head = head.copy()
        head[~np.asarray(head_evidence, dtype=bool)] = np.nan
    add(
        "head_movement_cm",
        _peak_magnitude(np.linalg.norm(head[active] - head[address], axis=1)) * 100,
        "cm",
        ("Head",),
    )
    add(
        "early_extension_cm",
        (hip[impact] - hip[address]) @ ball * 100,
        "cm",
        ("Hip",),
        np.array([address, impact]),
        ("up", "ball"),
    )
    lateral = np.degrees(np.arctan2(spine @ target, spine @ up))
    add(
        "reverse_spine_deg",
        lateral[top],
        "deg",
        ("Hip", "Neck"),
        np.array([top]),
        ("up", "target"),
        spine_valid,
    )
    knee_markers = ("LHip", "LKnee", "LAnkle", "RHip", "RKnee", "RAnkle")
    knees = [
        (
            _joint_angle_series(seq, *chain)[address]
            if all(seq.has_marker(name) for name in chain)
            else float("nan")
        )
        for chain in (knee_markers[:3], knee_markers[3:])
    ]
    add("knee_flex_deg", float(np.mean(knees)), "deg", knee_markers, np.array([address]))
    lead = "L" if handedness == "right" else "R"
    arm_markers = (f"{lead}Shoulder", f"{lead}Elbow", f"{lead}Wrist")
    arm = (
        _joint_angle_series(seq, *arm_markers)[top]
        if all(seq.has_marker(name) for name in arm_markers)
        else float("nan")
    )
    add("lead_arm_deg", arm, "deg", arm_markers, np.array([top]))
    speed_frames = np.flatnonzero(
        np.abs(seq.times - seq.times[impact]) <= metrics_config.hand_speed_window_s
    )
    speed_peaks = []
    for wrist in ("LWrist", "RWrist"):
        trajectory = marker(wrist)
        with np.errstate(invalid="ignore", divide="ignore"):
            speed = np.linalg.norm(np.diff(trajectory, axis=0), axis=1) / np.diff(seq.times)
            fraction = (seq.times[1:-1] - seq.times[:-2]) / (seq.times[2:] - seq.times[:-2])
        interpolated = trajectory[:-2] + fraction[:, None] * (trajectory[2:] - trajectory[:-2])
        outliers = (
            np.linalg.norm(trajectory[1:-1] - interpolated, axis=1)
            > metrics_config.marker_outlier_distance_m
        )
        outlier_frames = np.flatnonzero(outliers) + 1
        speed[outlier_frames - 1] = np.nan
        speed[outlier_frames] = np.nan
        speed[(speed > metrics_config.max_marker_speed_ms) | (speed < 0)] = np.nan
        evidence = None if marker_support is None else marker_support.get(wrist)
        if evidence is not None and np.asarray(evidence).shape == (seq.n_frames,):
            observation_mask = np.asarray(evidence, dtype=bool)
            speed[~(observation_mask[:-1] & observation_mask[1:])] = np.nan
        half = max(1, round(metrics_config.turn_filter_window_s * seq.fps / 2))
        for index in range(half, len(speed) - half):
            segment = speed[index - half : index + half + 1]
            finite = segment[np.isfinite(segment)]
            if (
                finite.size
                and speed[index] > np.median(finite) * metrics_config.max_limb_length_ratio
            ):
                speed[index] = np.nan
        interval_times = (seq.times[:-1] + seq.times[1:]) / 2
        indices = np.flatnonzero(
            np.abs(interval_times - seq.times[impact]) <= metrics_config.hand_speed_window_s
        )
        fraction = np.isfinite(speed[indices]).mean() if indices.size else 0
        speed_peaks.append(
            _peak_magnitude(speed[indices])
            if fraction >= metrics_config.min_supported_fraction
            else float("nan")
        )
    speed = _peak_magnitude(np.asarray(speed_peaks))
    add("hand_speed_impact_ms", speed, "m/s", ("LWrist", "RWrist"), speed_frames)
    hands = (marker("LWrist") + marker("RWrist")) / 2
    path = hands[top] - hands[address]
    height = np.dot(path, up)
    path_horizontal = np.linalg.norm(path - height * up)
    plane = (
        np.degrees(np.arctan2(height, path_horizontal))
        if np.linalg.norm(path) >= metrics_config.min_projected_width_m
        else float("nan")
    )
    add("swing_plane_deg", plane, "deg", ("LWrist", "RWrist"), np.array([address, top]), ("up",))
    return MetricsReport(phases=phases, metrics=results, reference_frame=reference.to_dict())
