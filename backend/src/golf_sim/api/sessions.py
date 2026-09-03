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


# The default group a swing belongs to until it's explicitly moved. Reference
# swings (e.g. tour-pro captures) go under PRO_GROUP so the UI can show them in
# a separate section that gives users a green-metric benchmark to compare to.
DEFAULT_GROUP = "My Swings"
PRO_GROUP = "Professional Swings"


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
                # grouping/label let the UI file swings under "My Swings" vs
                # "Professional Swings" and show a friendly name (e.g. "Rory
                # McIlroy Iron Swing") instead of the raw timestamp id
                "group": metadata.get("group") or DEFAULT_GROUP,
                "label": metadata.get("label") or None,
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


def set_session_meta(
    data_dir: Path,
    session_id: str,
    *,
    group: str | None = None,
    label: str | None = None,
) -> dict:
    """Move a swing into a group and/or give it a friendly name, persisted in
    the session's metadata.json so it survives reprocessing. Only the fields
    passed are touched; an empty string clears a label / resets the group to
    the default. Returns the resulting {id, group, label}."""
    session_dir = session_dir_for(data_dir, session_id)
    meta_path = session_dir / "metadata.json"
    try:
        metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        metadata = {}

    if group is not None:
        metadata["group"] = group.strip() or DEFAULT_GROUP
    if label is not None:
        cleaned = label.strip()
        if cleaned:
            metadata["label"] = cleaned
        else:
            metadata.pop("label", None)

    meta_path.write_text(json.dumps(metadata, indent=2))
    return {
        "id": session_id,
        "group": metadata.get("group") or DEFAULT_GROUP,
        "label": metadata.get("label") or None,
    }


def delete_session_media(data_dir: Path, session_id: str) -> dict:
    """Delete a session's video files (raw clips + pose-overlay debug videos)
    to reclaim disk space, while preserving metrics.json/metadata.json so the
    stats history survives. Returns how many files were removed and the bytes
    freed."""
    session_dir = session_dir_for(data_dir, session_id)
    removed = 0
    freed = 0
    for video in session_dir.rglob("*.mp4"):
        try:
            freed += video.stat().st_size
            video.unlink()
            removed += 1
        except OSError:
            # a locked/already-gone file must not abort the whole cleanup
            continue
    return {"deleted": removed, "bytes_freed": freed}


def delete_all_session_media(data_dir: Path) -> dict:
    """Delete the video files of *every* session (raw clips + pose-overlay
    debug videos) to reclaim disk space in bulk, while preserving each
    session's metrics.json/metadata.json so the stats history survives.
    Returns totals plus the number of sessions that had videos removed."""
    root = sessions_root(data_dir)
    removed = 0
    freed = 0
    sessions_cleared = 0
    if not root.is_dir():
        return {"deleted": 0, "bytes_freed": 0, "sessions_cleared": 0}
    for session_dir in root.iterdir():
        if not session_dir.is_dir():
            continue
        session_removed = 0
        for video in session_dir.rglob("*.mp4"):
            try:
                freed += video.stat().st_size
                video.unlink()
                session_removed += 1
            except OSError:
                # a locked/already-gone file must not abort the whole cleanup
                continue
        removed += session_removed
        if session_removed:
            sessions_cleared += 1
    return {"deleted": removed, "bytes_freed": freed, "sessions_cleared": sessions_cleared}


def sessions_stats(data_dir: Path) -> list[dict]:
    """Per-session metric values across every processed swing, oldest-first,
    for the stats/trend view. Reads only metrics.json (which survives video
    deletion), so the history remains after clips are cleared."""
    root = sessions_root(data_dir)
    if not root.is_dir():
        return []
    out = []
    for session_dir in root.iterdir():
        if not session_dir.is_dir():
            continue
        if (session_dir / "calibration_shot.json").exists():
            continue
        metrics_path = session_dir / "metrics.json"
        if not metrics_path.exists():
            continue
        try:
            data = json.loads(metrics_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        meta_path = session_dir / "metadata.json"
        try:
            metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            metadata = {}
        out.append(
            {
                "id": session_dir.name,
                "created_at": metadata.get("created_at"),
                "metrics": _json_safe(data.get("metrics", [])),
            }
        )
    # oldest-first so the frontend can plot a left-to-right time series
    out.sort(key=_sort_stamp)
    return out


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
