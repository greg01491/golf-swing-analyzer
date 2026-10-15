"""Integration test: analyze_session's real output includes usable
p_positions + ideal_frame data, not just the isolated unit pieces."""

import hashlib
import json

import numpy as np

from golf_sim.analysis.cli import (
    _marker_observation_support,
    _reference_for_session,
    analyze_session,
)
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
        assert set(p) >= {
            "name",
            "label",
            "frame_index",
            "time_s",
            "available",
            "detected",
            "estimate_reason",
            "unavailable_reason",
            "ideal_frame",
        }
        assert isinstance(p["available"], bool)
        assert isinstance(p["detected"], bool)
        assert "LShoulder" in p["ideal_frame"]
        assert len(p["ideal_frame"]["LShoulder"]) == 3


def test_reference_must_match_ground_provenance_and_trc(tmp_path, synthetic_swing_full):
    path = tmp_path / "swing.trc"
    _write_trc(synthetic_swing_full, path)
    evidence = {
        "source": "calibrated_ground",
        "validated": True,
        "up": [0, 0, 1],
        "source_trc_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    reference = _reference_for_session(
        synthetic_swing_full, {"analysis_reference": evidence}, path, "right"
    )
    assert reference.status != "valid"
    assert reference.source != "calibrated_ground"

    evidence["source"] = "checkerboard"
    assert (
        _reference_for_session(
            synthetic_swing_full, {"analysis_reference": evidence}, path, "right"
        ).status
        != "valid"
    )
    evidence["source"] = "calibrated_ground"
    evidence["source_trc_sha256"] = "another-session"
    assert (
        _reference_for_session(
            synthetic_swing_full, {"analysis_reference": evidence}, path, "right"
        ).status
        != "valid"
    )


def test_camera_motion_contradicts_held_head_but_not_observed_stillness(
    tmp_path, synthetic_swing_full, monkeypatch
):
    def observations(session_dir, camera_role, frame):
        points = np.zeros((26, 3))
        points[:, 0] = frame * 3
        points[:, 2] = 1
        return points

    monkeypatch.setattr("golf_sim.analysis.cli._load_keypoints", observations)
    support = _marker_observation_support(
        synthetic_swing_full, tmp_path, ["camera_1", "camera_2"], _FakeConfig().metrics
    )
    assert not support["Head"][60]
    assert support["LWrist"][60]

    def still_observations(session_dir, camera_role, frame):
        points = observations(session_dir, camera_role, frame)
        points[17, :2] = 100
        return points

    monkeypatch.setattr("golf_sim.analysis.cli._load_keypoints", still_observations)
    support = _marker_observation_support(
        synthetic_swing_full, tmp_path, ["camera_1", "camera_2"], _FakeConfig().metrics
    )
    assert support["Head"][60]


def test_cli_reports_unavailable_values_and_incomplete_assessment(tmp_path, monkeypatch, capsys):
    from golf_sim.analysis.cli import main

    output = tmp_path / "metrics.json"
    output.write_text(
        json.dumps(
            {
                "phases": {"address_frame": 0, "top_frame": 10, "impact_frame": 20},
                "metrics": [
                    {
                        "name": "shoulder_turn_deg",
                        "value": None,
                        "unit": "deg",
                        "status": "unavailable",
                        "in_range": None,
                        "range": None,
                    }
                ],
                "p_positions": [],
                "tips": [],
            }
        )
    )
    monkeypatch.setattr("golf_sim.analysis.cli.analyze_session", lambda *_: output)
    monkeypatch.setattr("golf_sim.analysis.cli.load_config", _FakeConfig)
    monkeypatch.setattr("sys.argv", ["analysis", str(tmp_path)])

    main()

    rendered = capsys.readouterr().out
    assert "unavailable" in rendered
    assert "assessment incomplete" in rendered
    assert "Nice swing" not in rendered
