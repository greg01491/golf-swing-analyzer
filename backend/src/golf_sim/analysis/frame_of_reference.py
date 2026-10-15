"""Evidence-bearing analysis references and legacy axis-based overlay helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from golf_sim.trc import LandmarkSequence


@dataclass
class AnalysisReference:
    up: np.ndarray | None
    target: np.ndarray | None = None
    ball: np.ndarray | None = None
    source: str = "provided"
    status: str = "valid"
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name in ("up", "target", "ball"):
            value = getattr(self, name)
            if value is None:
                continue
            vector = np.asarray(value, dtype=float)
            if vector.shape != (3,) or not np.isfinite(vector).all():
                raise ValueError(f"{name} must be a finite 3D vector")
            if name != "up" and self.up is not None:
                vector = vector - np.dot(vector, self.up) * self.up
            length = np.linalg.norm(vector)
            if length <= np.finfo(float).eps:
                raise ValueError(f"{name} must have nonzero length")
            setattr(self, name, vector / length)
        if self.target is not None and self.ball is not None:
            if not np.isclose(np.dot(self.target, self.ball), 0.0):
                raise ValueError("target and ball directions must be perpendicular")
        if self.up is None:
            self.status = "unavailable"
        if self.status not in {"valid", "estimated", "unavailable"}:
            raise ValueError("invalid reference status")

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "status": self.status,
            "reasons": list(self.reasons),
            **{
                name: None if getattr(self, name) is None else getattr(self, name).tolist()
                for name in ("up", "target", "ball")
            },
        }


def infer_reference(seq: LandmarkSequence, handedness: str = "right") -> AnalysisReference:
    if not all(seq.has_marker(name) for name in ("Hip", "LAnkle", "RAnkle")):
        return AnalysisReference(
            None, source="body", reasons=["missing_reference: hips and both ankles are required"]
        )
    feet = (seq.marker("LAnkle") + seq.marker("RAnkle")) / 2
    lower = seq.marker("Hip") - feet
    usable = lower[np.isfinite(lower).all(axis=1)]
    if not usable.size:
        return AnalysisReference(
            None, source="body", reasons=["missing_reference: no usable body axis"]
        )
    up = np.median(usable, axis=0)
    if np.linalg.norm(up) <= np.finfo(float).eps:
        return AnalysisReference(
            None, source="body", reasons=["degenerate_reference: hips coincide with feet"]
        )
    up /= np.linalg.norm(up)
    stance = np.nanmedian(seq.marker("LAnkle") - seq.marker("RAnkle"), axis=0)
    stance -= np.dot(stance, up) * up
    target = None
    if np.isfinite(stance).all() and np.linalg.norm(stance) > np.finfo(float).eps:
        target = stance * (1 if handedness == "right" else -1)
    if seq.has_marker("Neck"):
        torso = seq.marker("Neck") - seq.marker("Hip")
    elif seq.has_marker("LShoulder") and seq.has_marker("RShoulder"):
        torso = (seq.marker("LShoulder") + seq.marker("RShoulder")) / 2 - seq.marker("Hip")
    else:
        torso = np.empty((0, 3))
    finite_torso = torso[np.isfinite(torso).all(axis=1)]
    if finite_torso.size and np.dot(np.median(finite_torso, axis=0), up) <= 0:
        return AnalysisReference(
            up,
            target=target,
            source="body_lower_limb",
            status="unavailable",
            reasons=["conflicting_body_reference: reconstructed torso and legs disagree about up"],
        )
    return AnalysisReference(
        up,
        target=target,
        source="body_lower_limb",
        status="estimated",
        reasons=["estimated_ground: body alignment is not a calibrated floor normal"],
    )


def vertical_axis(seq: LandmarkSequence) -> tuple[int, float]:
    """Returns (axis_index, sign) such that coords[..., axis] * sign is height."""
    reference = infer_reference(seq)
    if reference.up is None:
        raise ValueError("vertical reference is unavailable")
    axis = int(np.argmax(np.abs(reference.up)))
    return axis, float(np.sign(reference.up[axis]))


def horizontal_angle_series(
    seq: LandmarkSequence, left_marker: str, right_marker: str, reference_frame: int
) -> np.ndarray:
    """Per-frame signed rotation (degrees) of the left->right body line in the
    horizontal plane, relative to its orientation at reference_frame."""
    up_axis, _ = vertical_axis(seq)
    horizontal_axes = [i for i in range(3) if i != up_axis]

    line = seq.marker(right_marker) - seq.marker(left_marker)
    u = line[:, horizontal_axes[0]]
    v = line[:, horizontal_axes[1]]
    angles = np.degrees(np.arctan2(v, u))
    relative = angles - angles[reference_frame]
    # wrap to [-180, 180] so a turn through the axis seam doesn't jump
    return (relative + 180) % 360 - 180
