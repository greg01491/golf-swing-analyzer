"""Session listing/detail helpers for the API layer -- the only reads the
API does against the session store's on-disk layout."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from golf_sim.trc import read_trc


def _json_safe(value):
    """Replace non-finite floats (NaN/Inf) with None throughout a nested
    structure. metrics.json can legitimately contain NaN -- a metric derived
    from a keypoint the pose model couldn't track in some frames -- and
    Starlette's JSON encoder rejects NaN (allow_nan=False), 500-ing the whole
    session-detail response. The UI already treats a null metric as
    'unavailable'."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def sessions_root(data_dir: Path) -> Path:
    return Path(data_dir) / "sessions"


def _sort_stamp(entry: dict) -> str:
    """Newest-first sort key: normalized UTC timestamp when metadata has one
    (session folder names changed format once, so name ordering alone would
    interleave old and new sessions wrongly); corrupt/unknown sort last."""
    created_at = entry.get("created_at")
    if created_at:
        try:
            return datetime.fromisoformat(created_at).astimezone(UTC).isoformat()
        except ValueError:
            pass
    return ""


def list_sessions(data_dir: Path) -> list[dict]:
    root = sessions_root(data_dir)
    if not root.is_dir():
        return []
    out = []
    for session_dir in sorted(root.iterdir(), reverse=True):
        if not session_dir.is_dir():
            continue
        if (session_dir / "calibration_shot.json").exists():
            continue  # wizard captures live in /api/calibration/shots, not the swing list
        meta_path = session_dir / "metadata.json"
        try:
            metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            # one corrupt session must not take down the whole browser (NFR5)
            metadata = {}
        out.append(
            {
                "id": session_dir.name,
                "created_at": metadata.get("created_at"),
                "cameras": sorted(p.stem for p in session_dir.glob("camera_*.mp4")),
                "has_pose": (session_dir / "pose2sim" / "pose").is_dir(),
                "has_3d": (
                    bool(list((session_dir / "pose2sim" / "pose-3d").glob("*.trc")))
                    if (session_dir / "pose2sim" / "pose-3d").is_dir()
                    else False
                ),
                "has_metrics": (session_dir / "metrics.json").exists(),
            }
        )
    out.sort(key=_sort_stamp, reverse=True)
    return out


def session_dir_for(data_dir: Path, session_id: str) -> Path:
    # basename-only lookup so a crafted id can't escape the sessions root
    if Path(session_id).name != session_id:
        raise FileNotFoundError(f"invalid session id: {session_id!r}")
    session_dir = sessions_root(data_dir) / session_id
    if not session_dir.is_dir():
        raise FileNotFoundError(f"no such session: {session_id}")
    return session_dir


def session_detail(data_dir: Path, session_id: str) -> dict:
    session_dir = session_dir_for(data_dir, session_id)
    meta_path = session_dir / "metadata.json"
    metrics_path = session_dir / "metrics.json"
    pose_dir = session_dir / "pose2sim" / "pose"
    return {
        "id": session_id,
        "metadata": json.loads(meta_path.read_text()) if meta_path.exists() else {},
        "metrics": (
            _json_safe(json.loads(metrics_path.read_text())) if metrics_path.exists() else None
        ),
        "cameras": sorted(p.stem for p in session_dir.glob("camera_*.mp4")),
        # cameras with a pose-overlay debug video (skeleton drawn on the
        # golfer) available -- lets the player offer an overlay toggle
        "overlay_cameras": (
            sorted(p.stem.removesuffix("_pose") for p in pose_dir.glob("camera_*_pose.mp4"))
            if pose_dir.is_dir()
            else []
        ),
    }


def session_landmarks(data_dir: Path, session_id: str) -> dict:
    """3D landmark sequence as JSON for the skeleton player. Prefers the
    filtered TRC."""
    session_dir = session_dir_for(data_dir, session_id)
    pose3d = session_dir / "pose2sim" / "pose-3d"
    candidates = sorted(pose3d.glob("*_filt_*.trc")) or sorted(pose3d.glob("*.trc"))
    if not candidates:
        raise FileNotFoundError(f"session {session_id} has no 3D landmarks")
    seq = read_trc(candidates[-1])
    return {
        "source": candidates[-1].name,
        "marker_names": seq.marker_names,
        "fps": seq.fps,
        "times": seq.times.tolist(),
        # NaNs aren't valid JSON -- the frontend gets nulls
        "frames": [
            [[None if c != c else round(c, 4) for c in marker] for marker in frame]
            for frame in seq.coords.tolist()
        ],
    }
