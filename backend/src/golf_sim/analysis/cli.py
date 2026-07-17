"""Compute swing metrics for a session (Phase 5 dev entrypoint).

    python -m golf_sim.analysis.cli <session_dir>|--latest

Reads the filtered TRC from the session's pose-3d output (falling back to
the unfiltered one) and writes metrics.json into the session folder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from golf_sim.analysis.metrics import compute_metrics
from golf_sim.analysis.tips import generate_tips, tips_to_dicts
from golf_sim.config import REPO_ROOT, load_config
from golf_sim.trc import read_trc


def pick_trc(session_dir: Path) -> Path:
    pose3d = session_dir / "pose2sim" / "pose-3d"
    filtered = sorted(pose3d.glob("*_filt_*.trc"))
    if filtered:
        return filtered[-1]
    unfiltered = sorted(pose3d.glob("*.trc"))
    if unfiltered:
        return unfiltered[-1]
    raise FileNotFoundError(
        f"no .trc under {pose3d} -- run `python -m golf_sim.pose.cli full` first"
    )


def analyze_session(session_dir: Path, config) -> Path:
    trc_path = pick_trc(session_dir)
    seq = read_trc(trc_path)
    report = compute_metrics(seq, config.metrics)
    tips = generate_tips(report)

    out_path = session_dir / "metrics.json"
    payload = {"source_trc": trc_path.name, **report.to_dict(), "tips": tips_to_dicts(tips)}
    out_path.write_text(json.dumps(payload, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", nargs="?", type=Path)
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()

    config = load_config()
    if args.latest:
        sessions = sorted((REPO_ROOT / config.storage.data_dir / "sessions").iterdir())
        session_dir = sessions[-1]
    elif args.session_dir is not None:
        session_dir = args.session_dir
    else:
        raise SystemExit("pass a session_dir or --latest")

    out_path = analyze_session(session_dir, config)
    print(f"metrics written to {out_path}\n")
    report = json.loads(out_path.read_text())
    phases = report["phases"]
    print(
        f"phases: address={phases['address_frame']} top={phases['top_frame']} "
        f"impact={phases['impact_frame']}"
    )
    for metric in report["metrics"]:
        flag = (
            ""
            if metric["in_range"] is None
            else ("  OK" if metric["in_range"] else "  ** OUT OF RANGE **")
        )
        print(f"  {metric['name']}: {metric['value']} {metric['unit']}{flag}")

    if report["tips"]:
        print("\ntips:")
        for i, tip in enumerate(report["tips"], 1):
            print(f"  {i}. [{tip['metric']} {tip['direction']}] {tip['text']}")
    else:
        print("\nno tips -- everything in range. Nice swing.")


if __name__ == "__main__":
    main()
