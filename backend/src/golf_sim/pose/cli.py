"""Run 2D pose estimation over a saved session (Phase 3 dev entrypoint).

python -m golf_sim.pose.cli <session_dir>
python -m golf_sim.pose.cli --latest      # most recent session in data/
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from golf_sim.config import REPO_ROOT, load_config
from golf_sim.pose.estimate import run_pose_estimation


def _latest_session(data_dir: Path) -> Path:
    sessions = sorted((data_dir / "sessions").iterdir())
    if not sessions:
        raise FileNotFoundError(f"no sessions found under {data_dir / 'sessions'}")
    return sessions[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", nargs="?", type=Path)
    parser.add_argument("--latest", action="store_true", help="use most recent session")
    args = parser.parse_args()

    config = load_config()
    if args.latest:
        session_dir = _latest_session(REPO_ROOT / config.storage.data_dir)
    elif args.session_dir is not None:
        session_dir = args.session_dir
    else:
        parser.error("pass a session_dir or --latest")

    print(f"running pose estimation on {session_dir} (mode={config.pose.mode})...")
    start = time.monotonic()
    result = run_pose_estimation(session_dir, config.pose)
    elapsed = time.monotonic() - start

    print(f"\ndone in {elapsed:.1f}s")
    for landmark_dir in result.landmark_dirs:
        n = len(list(landmark_dir.glob("*.json")))
        print(f"  {landmark_dir.name}: {n} frames of landmarks")
    for video in result.overlay_videos:
        print(f"  overlay: {video}")


if __name__ == "__main__":
    main()
