"""Writes a captured swing to disk as a session: one video file per camera
plus metadata.json (FR11)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import cv2

from golf_sim.capture.frame import Frame


def write_clip(frames: list[Frame], path: Path, fps: float) -> None:
    if not frames:
        raise ValueError("cannot write a clip with no frames")
    height, width = frames[0].image.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    try:
        for frame in frames:
            writer.write(frame.image)
    finally:
        writer.release()


class SessionWriter:
    def __init__(self, data_dir: Path | str):
        self.sessions_dir = Path(data_dir) / "sessions"

    def write_session(
        self,
        camera_clips: dict[str, list[Frame]],
        camera_meta: dict[str, dict],
        pre_capture_delay_s: float,
        capture_duration_s: float,
    ) -> Path:
        created_at = datetime.now(UTC)
        session_id = f"{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(parents=True)

        cameras_metadata = {}
        for role, frames in camera_clips.items():
            meta = camera_meta[role]
            filename = f"{role}.mp4"
            write_clip(frames, session_dir / filename, fps=meta["fps"])
            cameras_metadata[role] = {**meta, "frame_count": len(frames), "file": filename}

        metadata = {
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "pre_capture_delay_s": pre_capture_delay_s,
            "capture_duration_s": capture_duration_s,
            "cameras": cameras_metadata,
        }
        (session_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        return session_dir
