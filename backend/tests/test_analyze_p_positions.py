"""Integration test: analyze_session's real output includes usable
p_positions + ideal_frame data, not just the isolated unit pieces."""

import json

from golf_sim.analysis.cli import analyze_session
from golf_sim.config import AnalysisConfig, MetricsConfig, ReferenceRange


def _write_trc(seq, path) -> None:
    lines = [
        "PathFileType\t4\t(X/Y/Z)\ttest.trc",
        "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames",
        f"{seq.fps}\t{seq.fps}\t{seq.n_frames}\t{len(seq.marker_names)}\tm\t{seq.fps}\t0\t{seq.n_frames}",
        "Frame#\tTime\t" + "\t\t\t".join(seq.marker_names) + "\t\t",
        "\t\t" + "\t".join(f"X{i + 1}\tY{i + 1}\tZ{i + 1}" for i in range(len(seq.marker_names))),
        "",
    ]
    for i in range(seq.n_frames):
        row = [str(i), f"{seq.times[i]:.6f}"]
        for m in range(len(seq.marker_names)):
            row.extend(f"{c:.6f}" for c in seq.coords[i, m])
        lines.append("\t".join(row))
    path.write_text("\n".join(lines))


class _FakeConfig:
    def __init__(self):
        self.metrics = MetricsConfig(
            reference_ranges={
                "shoulder_turn_deg": ReferenceRange(min=80, max=100),
                "hip_turn_deg": ReferenceRange(min=40, max=55),
            }
        )
        self.analysis = AnalysisConfig(golfer_handedness="right")


def test_analyze_session_writes_p_positions_with_ideal_frames(tmp_path, synthetic_swing_full):
    session_dir = tmp_path / "session"
    pose3d = session_dir / "pose2sim" / "pose-3d"
    pose3d.mkdir(parents=True)
    _write_trc(synthetic_swing_full, pose3d / "swing_0-179.trc")

    out_path = analyze_session(session_dir, _FakeConfig())
    payload = json.loads(out_path.read_text())

    assert "p_positions" in payload
    assert [p["name"] for p in payload["p_positions"]] == [f"P{i}" for i in range(1, 11)]
    for p in payload["p_positions"]:
        assert set(p) >= {"name", "label", "frame_index", "time_s", "ideal_frame"}
        assert "LShoulder" in p["ideal_frame"]
        assert len(p["ideal_frame"]["LShoulder"]) == 3
