"""H.264 transcoding for browser-playable clips.

OpenCV's VideoWriter can only produce mp4v (MPEG-4 Part 2) without a
separately-downloaded OpenH264 DLL, and Chromium/Electron cannot decode
mp4v at all -- found live: every session played as a black frame stuck at
0:00 in the UI, even though the files were fine on disk. Every clip meant
for in-app playback (capture clips, pose overlay videos) runs through
ensure_h264() after writing.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def ensure_h264(path: Path) -> bool:
    """Re-encodes the clip at `path` to H.264 in place. Returns True on
    success. On any failure the original file is left untouched -- an
    unplayable-in-browser clip still beats a lost capture."""
    path = Path(path)
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg = get_ffmpeg_exe()
    except Exception:
        logger.exception("ffmpeg unavailable -- clip %s left as mp4v", path)
        return False

    # dot-prefixed so a crash mid-transcode can't leave a leftover that
    # matches the session code's camera_*.mp4 globs (which would surface a
    # phantom camera in listings); keeps the .mp4 extension ffmpeg uses to
    # pick the container
    tmp = path.with_name(f".transcoding_{path.name}")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        # yuv420p is the only pixel format every browser decodes; ffmpeg
        # would otherwise keep yuv444/whatever the source used
        "-pix_fmt",
        "yuv420p",
        # moov atom up front so playback can start before the full download
        "-movflags",
        "+faststart",
        "-an",
        str(tmp),
    ]
    try:
        # CREATE_NO_WINDOW: without it, every capture flashes a console
        # window when the backend runs under the packaged (windowed) app
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.run(
            cmd, check=True, capture_output=True, timeout=120, creationflags=creationflags
        )
        os.replace(tmp, path)
        return True
    except Exception as exc:
        stderr = getattr(exc, "stderr", b"") or b""
        logger.error(
            "H.264 transcode failed for %s -- keeping mp4v original: %s %s",
            path,
            exc,
            stderr.decode(errors="replace")[-500:],
        )
        tmp.unlink(missing_ok=True)
        return False
