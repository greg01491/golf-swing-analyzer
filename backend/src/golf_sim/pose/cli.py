"""Pose pipeline dev entrypoints (Phases 3-4).

python -m golf_sim.pose.cli estimate <session_dir>|--latest    # 2D landmarks
python -m golf_sim.pose.cli reconstruct <session_dir>|--latest # 3D from 2D
python -m golf_sim.pose.cli full <session_dir>|--latest        # both stages
python -m golf_sim.pose.cli calibrate                          # rig checkerboard calibration
python -m golf_sim.pose.cli status                             # calibration health
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from golf_sim.config import REPO_ROOT, load_config
from golf_sim.pose.calibrate import calibration_status, run_checkerboard_calibration
from golf_sim.pose.estimate import run_pose_estimation
from golf_sim.pose.reconstruct import run_reconstruction


def _latest_session(data_dir: Path) -> Path:
    sessions = sorted((data_dir / "sessions").iterdir())
    if not sessions:
        raise FileNotFoundError(f"no sessions found under {data_dir / 'sessions'}")
    return sessions[-1]


def _resolve_session(args, config) -> Path:
    if args.latest:
        return _latest_session(REPO_ROOT / config.storage.data_dir)
    if args.session_dir is not None:
        return args.session_dir
    raise SystemExit("pass a session_dir or --latest")


def _estimate(session_dir: Path, config) -> None:
    print(f"2D pose estimation on {session_dir} (mode={config.pose.mode})...")
    start = time.monotonic()
    result = run_pose_estimation(session_dir, config.pose)
    print(f"done in {time.monotonic() - start:.1f}s")
    for landmark_dir in result.landmark_dirs:
        n = len(list(landmark_dir.glob("*.json")))
        print(f"  {landmark_dir.name}: {n} frames of landmarks")
    for video in result.overlay_videos:
        print(f"  overlay: {video}")


def _reconstruct(session_dir: Path, config) -> None:
    print(f"3D reconstruction on {session_dir}...")
    start = time.monotonic()
    result = run_reconstruction(session_dir, config)
    print(f"done in {time.monotonic() - start:.1f}s")
    for trc in result.trc_files:
        print(f"  3D landmarks: {trc}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("estimate", "reconstruct", "full"):
        sub = subparsers.add_parser(name)
        sub.add_argument("session_dir", nargs="?", type=Path)
        sub.add_argument("--latest", action="store_true")
    subparsers.add_parser("calibrate")
    subparsers.add_parser("status")

    args = parser.parse_args()
    config = load_config()

    if args.command == "status":
        status = calibration_status(config.calibration)
        if not status.exists:
            print("calibration: MISSING -- run `python -m golf_sim.pose.cli calibrate`")
        else:
            staleness = " (STALE -- recalibration recommended)" if status.stale else ""
            print(f"calibration: {status.file} -- {status.age_days:.0f} days old{staleness}")
    elif args.command == "calibrate":
        calib_file = run_checkerboard_calibration(config.calibration)
        print(f"calibration written to {calib_file}")
    elif args.command == "estimate":
        _estimate(_resolve_session(args, config), config)
    elif args.command == "reconstruct":
        _reconstruct(_resolve_session(args, config), config)
    elif args.command == "full":
        session_dir = _resolve_session(args, config)
        _estimate(session_dir, config)
        _reconstruct(session_dir, config)


if __name__ == "__main__":
    main()
