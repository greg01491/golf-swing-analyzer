"""Turn captured sessions into calibration input frames.

The rig's cameras are held open by the running backend, so a separate
calibration-capture tool can't open them. Instead: the user holds the
printed checkerboard in view and we fire normal manual triggers -- each
session is already a synchronized recording from both cameras -- then this
module samples frames out of those session clips into the layout Pose2Sim's
calibration expects (config/calibration/{intrinsics,extrinsics}/...).

    python -m golf_sim.pose.board_frames intrinsics <session_dir> [more sessions...]
    python -m golf_sim.pose.board_frames extrinsics <session_dir>
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from golf_sim.config import REPO_ROOT, load_config


def _rig_dir() -> Path:
    config = load_config()
    path = Path(config.calibration.dir)
    return path if path.is_absolute() else REPO_ROOT / path


def extract_intrinsics_frames(
    session_dirs: list[Path], rig_dir: Path, frames_per_clip: int = 6
) -> None:
    """Sample frames evenly from each session clip into
    intrinsics/int_camera_N_img/ (varied board poses per frame)."""
    for session_dir in session_dirs:
        for clip in sorted(Path(session_dir).glob("camera_*.mp4")):
            out_dir = rig_dir / "intrinsics" / f"int_{clip.stem}_img"
            out_dir.mkdir(parents=True, exist_ok=True)
            cap = cv2.VideoCapture(str(clip))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for i in range(frames_per_clip):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(i * total / frames_per_clip))
                ok, frame = cap.read()
                if ok:
                    name = f"{Path(session_dir).name}_{i:02d}.png"
                    cv2.imwrite(str(out_dir / name), frame)
            cap.release()
            n = len(list(out_dir.glob("*.png")))
            print(f"{clip.stem}: {n} intrinsics frames total in {out_dir}")


def extract_extrinsics_frames(session_dir: Path, rig_dir: Path) -> None:
    """One mid-clip still per camera (board lying flat at the hitting spot)."""
    out_dir = rig_dir / "extrinsics"
    out_dir.mkdir(parents=True, exist_ok=True)
    for clip in sorted(Path(session_dir).glob("camera_*.mp4")):
        cap = cv2.VideoCapture(str(clip))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise RuntimeError(f"could not read a frame from {clip}")
        out = out_dir / f"{clip.stem}_ext.png"
        cv2.imwrite(str(out), frame)
        print(f"{clip.stem}: extrinsics still -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["intrinsics", "extrinsics"])
    parser.add_argument("sessions", nargs="+", type=Path)
    args = parser.parse_args()

    rig_dir = _rig_dir()
    if args.kind == "intrinsics":
        extract_intrinsics_frames(args.sessions, rig_dir)
    else:
        extract_extrinsics_frames(args.sessions[0], rig_dir)


if __name__ == "__main__":
    main()
