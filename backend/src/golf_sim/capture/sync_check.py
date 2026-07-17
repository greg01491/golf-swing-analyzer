"""Validate real two-camera sync on actual hardware.

Our timestamping already shares one clock (both CameraStream threads stamp
frames with time.monotonic() in the same process -- plan.md Spike B), but
that doesn't rule out per-camera USB/driver latency differences on real
hardware. This tool measures that empirically: have someone clap or flash a
light in view of both cameras during a capture, then point this at the two
resulting clips -- it finds the frame each camera registers the event on and
reports the time offset between them.

Usage:
    python -m golf_sim.capture.sync_check camera_1.mp4 camera_2.mp4 [--tolerance-ms 33]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass
class FlashEvent:
    frame_index: int
    time_s: float
    fps: float


def detect_flash_frame(video_path: Path) -> FlashEvent:
    """Finds the frame with the largest brightness jump from the previous
    frame -- a clap/flash produces a sharp spike, unlike gradual lighting
    changes from the swing itself."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    try:
        prev_mean: float | None = None
        best_index = 0
        best_jump = -1.0
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            mean = float(frame.mean())
            if prev_mean is not None:
                jump = mean - prev_mean
                if jump > best_jump:
                    best_jump = jump
                    best_index = index
            prev_mean = mean
            index += 1
    finally:
        cap.release()

    if best_jump < 0:
        raise ValueError(
            f"{video_path}: could not detect a brightness event (empty/too-short clip)"
        )

    return FlashEvent(frame_index=best_index, time_s=best_index / fps, fps=fps)


def check_sync(path_a: Path, path_b: Path) -> dict:
    event_a = detect_flash_frame(path_a)
    event_b = detect_flash_frame(path_b)
    return {
        "camera_a": {
            "file": str(path_a),
            "flash_frame": event_a.frame_index,
            "time_s": event_a.time_s,
        },
        "camera_b": {
            "file": str(path_b),
            "flash_frame": event_b.frame_index,
            "time_s": event_b.time_s,
        },
        "offset_s": event_a.time_s - event_b.time_s,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("camera_a", type=Path)
    parser.add_argument("camera_b", type=Path)
    parser.add_argument(
        "--tolerance-ms",
        type=float,
        default=33.0,
        help="rule-of-thumb pass/fail threshold, default ~1 frame at 30fps",
    )
    args = parser.parse_args()

    result = check_sync(args.camera_a, args.camera_b)
    offset_ms = result["offset_s"] * 1000
    a, b = result["camera_a"], result["camera_b"]
    print(f"camera_a flash at frame {a['flash_frame']} ({a['time_s']:.3f}s)")
    print(f"camera_b flash at frame {b['flash_frame']} ({b['time_s']:.3f}s)")
    print(f"offset: {offset_ms:+.1f}ms")

    if abs(offset_ms) <= args.tolerance_ms:
        print(f"PASS -- within tolerance ({args.tolerance_ms:.1f}ms)")
    else:
        print(
            f"FAIL -- exceeds tolerance ({args.tolerance_ms:.1f}ms); investigate per-camera latency"
        )


if __name__ == "__main__":
    main()
