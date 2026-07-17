"""Quick 3D landmark QA visuals (Phase 4 exit criteria): read a Pose2Sim
.trc file and render the skeleton at sampled frames so a human can check the
reconstruction visibly matches the recorded motion.

    python -m golf_sim.pose.viewer <file.trc> [-o out.png]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

# Bone connections by Pose2Sim/HALPE marker name; pairs missing from a given
# file are skipped, so this works across pose models.
_SKELETON_EDGES = [
    ("Head", "Neck"),
    ("Neck", "RShoulder"),
    ("Neck", "LShoulder"),
    ("RShoulder", "RElbow"),
    ("RElbow", "RWrist"),
    ("LShoulder", "LElbow"),
    ("LElbow", "LWrist"),
    ("Neck", "Hip"),
    ("Hip", "RHip"),
    ("Hip", "LHip"),
    ("RHip", "RKnee"),
    ("RKnee", "RAnkle"),
    ("LHip", "LKnee"),
    ("LKnee", "LAnkle"),
    ("RAnkle", "RBigToe"),
    ("RAnkle", "RHeel"),
    ("LAnkle", "LBigToe"),
    ("LAnkle", "LHeel"),
]


def read_trc(path: Path) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Returns (marker_names, times [n_frames], coords [n_frames, n_markers, 3])."""
    lines = Path(path).read_text().splitlines()
    # line 3 (0-indexed): tab-separated marker names starting at column 2
    marker_names = [name for name in lines[3].split("\t")[2:] if name.strip()]
    rows = []
    for line in lines[5:]:
        if not line.strip():
            continue
        rows.append([float(v) if v.strip() else np.nan for v in line.split("\t")])
    data = np.array(rows)
    times = data[:, 1]
    coords = data[:, 2 : 2 + 3 * len(marker_names)].reshape(len(data), len(marker_names), 3)
    return marker_names, times, coords


def plot_frames(
    trc_path: Path, out_path: Path, num_frames: int = 6, elev: float = 20, azim: float = -70
) -> Path:
    """Render a grid of 3D skeleton poses sampled evenly across the clip."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    marker_names, times, coords = read_trc(trc_path)
    name_index = {name: i for i, name in enumerate(marker_names)}
    edges = [
        (name_index[a], name_index[b])
        for a, b in _SKELETON_EDGES
        if a in name_index and b in name_index
    ]

    frame_indices = np.linspace(0, len(coords) - 1, num_frames, dtype=int)
    cols = 3
    rows = int(np.ceil(num_frames / cols))
    fig = plt.figure(figsize=(5 * cols, 5 * rows))

    # shared bounds so the skeleton doesn't rescale between frames
    valid = coords[~np.isnan(coords).any(axis=2).all(axis=1)]
    center = np.nanmean(coords.reshape(-1, 3), axis=0)
    half_range = np.nanmax(np.abs(coords.reshape(-1, 3) - center)) * 1.1 if len(valid) else 1.0

    for plot_idx, frame_idx in enumerate(frame_indices):
        ax = fig.add_subplot(rows, cols, plot_idx + 1, projection="3d")
        frame = coords[frame_idx]
        ax.scatter(frame[:, 0], frame[:, 1], frame[:, 2], s=12)
        for a, b in edges:
            if not (np.isnan(frame[a]).any() or np.isnan(frame[b]).any()):
                ax.plot(*zip(frame[a], frame[b], strict=True), linewidth=2)
        ax.set_title(f"frame {frame_idx} (t={times[frame_idx]:.2f}s)")
        ax.set_xlim(center[0] - half_range, center[0] + half_range)
        ax.set_ylim(center[1] - half_range, center[1] + half_range)
        ax.set_zlim(center[2] - half_range, center[2] + half_range)
        ax.view_init(elev=elev, azim=azim)

    fig.tight_layout()
    fig.savefig(out_path, dpi=90)
    plt.close(fig)
    return Path(out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trc_file", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=None)
    parser.add_argument("--frames", type=int, default=6)
    args = parser.parse_args()

    out = args.out or args.trc_file.with_suffix(".qa.png")
    path = plot_frames(args.trc_file, out, num_frames=args.frames)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
