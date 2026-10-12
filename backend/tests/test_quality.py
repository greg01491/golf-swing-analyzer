import numpy as np

from golf_sim.analysis.cli import _wrist_visibility_by_camera
from golf_sim.analysis.quality import assess_tracking_quality
from golf_sim.trc import LandmarkSequence


def _seq(hands_per_frame: np.ndarray) -> LandmarkSequence:
    # minimal sequence with just the two wrist markers the assessor reads;
    # both wrists set equal so their midpoint is exactly hands_per_frame
    n = len(hands_per_frame)
    coords = np.zeros((n, 2, 3))
    coords[:, 0, :] = hands_per_frame
    coords[:, 1, :] = hands_per_frame
    return LandmarkSequence(
        times=np.arange(n) / 60.0, coords=coords, marker_names=["RWrist", "LWrist"]
    )


def test_clean_swing_is_reliable():
    # smooth, plausible-scale vertical arc (~1.4 m of travel)
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 0.7 * np.sin(t), np.zeros_like(t)], axis=1)
    q = assess_tracking_quality(_seq(hands))
    assert q.reliable is True
    assert q.warnings == []
    assert q.moving_fraction > 0.9
    assert q.swing_moving_fraction is None


def test_frozen_gapfilled_sequence_flagged():
    # mostly held (gap-filled) values: one position repeated, a couple jumps
    hands = np.zeros((100, 3))
    hands[50:] = [0.0, 1.0, 0.0]  # a single jump; every other step is 0
    q = assess_tracking_quality(_seq(hands))
    assert q.reliable is False
    assert any("whole-clip" in w for w in q.warnings)


def test_implausible_scale_flagged():
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 5.0 * np.sin(t), np.zeros_like(t)], axis=1)  # 5 m travel
    q = assess_tracking_quality(_seq(hands))
    assert q.reliable is False
    assert any("physically impossible" in w for w in q.warnings)


def test_stationary_clip_lead_in_and_finish_do_not_fail_swing_window():
    hands = np.zeros((100, 3))
    hands[20:41, 1] = np.linspace(0, 1, 21)
    quality = assess_tracking_quality(_seq(hands), swing_window=(20, 40))

    assert quality.moving_fraction < 0.6
    assert quality.swing_moving_fraction == 1.0
    assert quality.reliable is True
    assert quality.warnings == []


def test_low_active_swing_motion_is_named_separately_from_clip_pauses():
    hands = np.zeros((100, 3))
    hands[20:23, 1] = [0.0, 0.5, 1.0]
    quality = assess_tracking_quality(_seq(hands), swing_window=(20, 80))

    assert quality.swing_moving_fraction < 0.6
    assert any("address-to-impact" in warning for warning in quality.warnings)


def test_weak_camera_wrist_coverage_names_camera_and_wrist():
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 0.7 * np.sin(t), np.zeros_like(t)], axis=1)
    quality = assess_tracking_quality(
        _seq(hands),
        swing_window=(0, len(hands) - 1),
        camera_wrist_visibility={
            "camera_1": {"LWrist": 0.71, "RWrist": 0.96},
            "camera_2": {"LWrist": 0.99, "RWrist": 0.83},
        },
        camera_wrist_triangulation_coverage={
            "camera_1": {"LWrist": 1.0, "RWrist": 1.0},
            "camera_2": {"LWrist": 1.0, "RWrist": 1.0},
        },
    )

    assert quality.reliable is True
    assert quality.camera_wrist_visibility["camera_1"]["LWrist"] == 0.71
    assert any("camera_1 LWrist" in note and "71%" in note for note in quality.advisories)
    assert quality.warnings == []


def test_wrist_below_triangulation_cutoff_is_unreliable():
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 0.7 * np.sin(t), np.zeros_like(t)], axis=1)
    quality = assess_tracking_quality(
        _seq(hands),
        swing_window=(0, len(hands) - 1),
        camera_wrist_visibility={"camera_1": {"LWrist": 0.71, "RWrist": 0.96}},
        camera_wrist_triangulation_coverage={"camera_1": {"LWrist": 0.72, "RWrist": 1.0}},
    )

    assert quality.reliable is False
    assert any("triangulation confidence cutoff" in warning for warning in quality.warnings)
    assert any("71%" in note for note in quality.advisories)


def test_missing_wrist_confidence_preserves_motion_assessment():
    t = np.linspace(0, np.pi, 120)
    hands = np.stack([np.zeros_like(t), 0.7 * np.sin(t), np.zeros_like(t)], axis=1)
    quality = assess_tracking_quality(_seq(hands), swing_window=(0, len(hands) - 1))

    assert quality.reliable is True
    assert quality.camera_wrist_visibility is None


def test_camera_wrist_visibility_aggregates_missing_and_low_confidence_frames(tmp_path):
    import json

    pose_root = tmp_path / "pose2sim" / "pose"
    for camera, left_scores, right_scores in (
        ("camera_1", [0.9, 0.1, None], [0.9, 0.9, None]),
        ("camera_2", [0.9, 0.9, 0.9], [0.9, 0.9, 0.9]),
    ):
        camera_dir = pose_root / f"{camera}_json"
        camera_dir.mkdir(parents=True)
        for frame_index, (left, right) in enumerate(zip(left_scores, right_scores, strict=True)):
            people = []
            if left is not None:
                keypoints = np.ones((26, 3)).tolist()
                keypoints[9][2] = left
                keypoints[10][2] = right
                people = [{"pose_keypoints_2d": np.asarray(keypoints).reshape(-1).tolist()}]
            payload = {"people": people}
            (camera_dir / f"{camera}_{frame_index:06d}.json").write_text(json.dumps(payload))

    visibility = _wrist_visibility_by_camera(tmp_path, ["camera_1", "camera_2"], 0, 2)
    triangulation_visibility = _wrist_visibility_by_camera(
        tmp_path, ["camera_1", "camera_2"], 0, 2, confidence_threshold=0.3
    )

    assert visibility == {
        "camera_1": {"LWrist": 1 / 3, "RWrist": 2 / 3},
        "camera_2": {"LWrist": 1.0, "RWrist": 1.0},
    }
    assert triangulation_visibility == {
        "camera_1": {"LWrist": 1 / 3, "RWrist": 2 / 3},
        "camera_2": {"LWrist": 1.0, "RWrist": 1.0},
    }
