import hashlib
import json

import cv2
import numpy as np
import pytest

from golf_sim.config import CrownTrackingDiagnosticConfig
from golf_sim.diagnostics.crown_tracking import (
    HeadPointTracker,
    OperatorCrownSeed,
    OperatorCrownSeeds,
    run_head_tracking_diagnostic,
)


def _texture():
    return np.random.default_rng(7).integers(0, 256, (180, 220), dtype=np.uint8)


def test_stationary_image_does_not_follow_detector_jitter():
    image = _texture()
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig())
    assert tracker.update(image, np.array([90, 80, 0.9]))["candidate_xy"] is None
    candidates = []
    for offset in [3, -3, 4, -4, 2, -2]:
        result = tracker.update(image, np.array([90 + offset, 80, 0.9]))
        assert result["status"] == "image_consistent"
        candidates.append(result["candidate_xy"])
    assert np.max(np.linalg.norm(np.array(candidates) - [90, 80], axis=1)) < 0.1


@pytest.mark.parametrize("shift", [(2, 1), (6, 3)])
def test_real_image_translation_is_followed_without_averaging_lag(shift):
    image = _texture()
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig())
    tracker.update(image, np.array([70, 65, 0.9]))
    for frame in range(1, 9):
        displacement = np.array(shift) * frame
        moved = cv2.warpAffine(
            image, np.float32([[1, 0, displacement[0]], [0, 1, displacement[1]]]), (220, 180)
        )
        actual = np.array([70, 65]) + displacement
        observation = np.append(actual + [(-1) ** frame * 2, 0], 0.9)
        result = tracker.update(moved, observation)
        assert result["status"] == "image_consistent"
        assert np.linalg.norm(np.array(result["candidate_xy"]) - actual) < 0.5


def test_blank_images_and_missing_observations_are_not_filled():
    blank = np.zeros((180, 220), dtype=np.uint8)
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig())
    tracker.update(blank, np.array([90, 80, 0.9]))
    result = tracker.update(blank, np.array([90, 80, 0.9]))
    assert result["candidate_xy"] is None
    assert result["status"] == "insufficient_image_features"
    assert tracker.update(_texture(), None)["candidate_xy"] is None
    assert tracker.update(_texture(), np.array([90, 80, 0.1]))["candidate_xy"] is None


def test_occluded_image_rejects_point_despite_high_detector_confidence():
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig())
    image = _texture()
    tracker.update(image, np.array([90, 80, 0.9]))
    result = tracker.update(np.zeros_like(image), np.array([90, 80, 0.9]))
    assert result["candidate_xy"] is None
    assert result["status"] != "image_consistent"


def test_landmark_switch_is_rejected_instead_of_smoothly_invented():
    image = _texture()
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig())
    tracker.update(image, np.array([90, 80, 0.9]))
    result = tracker.update(image, np.array([120, 80, 0.9]))
    assert result["candidate_xy"] is None
    assert result["status"] in {"detector_disagreement", "insufficient_motion_inliers"}
    assert tracker.update(image, np.array([120, 80, 0.9]))["status"] == "seed_unverified"


def test_operator_seed_does_not_snap_back_to_displaced_detector_point():
    image = _texture()
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig(), operator_seeded=True)
    observation = np.array([120, 80, 0.9])
    assert tracker.update(image, observation)["status"] == "awaiting_operator_seed"
    seeded = tracker.update(image, observation, seed_xy=np.array([90, 80]))
    assert seeded["status"] == "operator_seed_recorded"
    assert seeded["candidate_xy"] is None
    result = tracker.update(image, np.array([123, 80, 0.9]))
    assert result["status"] == "image_consistent"
    assert np.linalg.norm(np.array(result["candidate_xy"]) - [90, 80]) < 0.1
    assert result["detector_distance_px"] > 30
    tracker.update(np.zeros_like(image), observation)
    assert tracker.update(image, observation)["status"] == "awaiting_operator_seed"
    assert tracker.update(image, observation)["candidate_xy"] is None


def test_operator_track_is_independent_of_detector_jumps_and_missing_observations():
    image = _texture()
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig(), operator_seeded=True)
    tracker.update(image, None, seed_xy=np.array([90, 80]))
    for observation in [
        np.array([180, 140, 0.9]),
        np.array([30, 20, 0.9]),
        None,
        np.array([120, 80, 0.1]),
    ]:
        result = tracker.update(image, observation)
        assert result["status"] == "image_consistent"
        assert np.linalg.norm(np.array(result["candidate_xy"]) - [90, 80]) < 0.1
    result = tracker.update(np.zeros_like(image), None)
    assert result["candidate_xy"] is None
    assert tracker.update(image, np.array([90, 80, 0.9]))["status"] == "awaiting_operator_seed"


def test_operator_track_follows_known_image_motion_without_detector_guidance():
    image = _texture()
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig(), operator_seeded=True)
    tracker.update(image, None, seed_xy=np.array([70, 65]))
    for frame in range(1, 9):
        displacement = np.array([6, 3]) * frame
        moved = cv2.warpAffine(
            image, np.float32([[1, 0, displacement[0]], [0, 1, displacement[1]]]), (220, 180)
        )
        result = tracker.update(moved, None)
        assert result["status"] == "image_consistent"
        assert np.linalg.norm(np.array(result["candidate_xy"]) - ([70, 65] + displacement)) < 0.5


def test_operator_seed_rejects_invalid_native_coordinates():
    tracker = HeadPointTracker(CrownTrackingDiagnosticConfig(), operator_seeded=True)
    with pytest.raises(ValueError, match="operator seed"):
        tracker.update(_texture(), np.array([120, 80, 0.9]), seed_xy=np.array([-1, 80]))


def test_diagnostic_writes_only_separate_outputs_and_never_authorizes_metrics(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    poses = source / "pose"
    poses.mkdir()
    video = source / "camera_1.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 60, (220, 180))
    image = cv2.cvtColor(_texture(), cv2.COLOR_GRAY2BGR)
    for frame in range(12):
        writer.write(image)
        points = np.zeros((26, 3))
        points[17] = [90 + frame % 2 * 3, 80, 0.9]
        (poses / f"camera_1_{frame:06d}.json").write_text(
            json.dumps({"people": [{"pose_keypoints_2d": points.ravel().tolist()}]})
        )
    writer.release()
    before = {path: path.read_bytes() for path in source.rglob("*") if path.is_file()}
    output = tmp_path / "diagnostic"

    summary = run_head_tracking_diagnostic(video, poses, output, CrownTrackingDiagnosticConfig())

    assert summary["frame_count"] == 12
    assert summary["image_supported_fraction"] > 0
    assert summary["diagnostic_only"] is True
    assert summary["eligible_for_metrics"] is False
    assert summary["anatomical_crown_verified"] is False
    assert len(json.loads((output / "comparison.json").read_text())["frames"]) == 12
    assert {path: path.read_bytes() for path in source.rglob("*") if path.is_file()} == before
    seed_file = tmp_path / "operator_seeds.json"
    seed = OperatorCrownSeed(
        case_id="test-camera_1",
        camera="camera_1",
        video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
        frame_index=0,
        native_width=220,
        native_height=180,
        x=75,
        y=70,
        confirmed_visible=True,
    )
    seed_file.write_text(OperatorCrownSeeds(annotations=[seed]).model_dump_json())
    seeded = run_head_tracking_diagnostic(
        video,
        poses,
        tmp_path / "operator-diagnostic",
        CrownTrackingDiagnosticConfig(),
        seed_file=seed_file,
    )
    assert seeded["operator_seed_frames"] == [0]
    assert seeded["status_counts"]["operator_seed_recorded"] == 1
    assert seeded["anatomical_crown_verified"] is False
    assert seeded["eligible_for_metrics"] is False
    seed.video_sha256 = "0" * 64
    seed_file.write_text(OperatorCrownSeeds(annotations=[seed]).model_dump_json())
    with pytest.raises(ValueError, match="exact video"):
        run_head_tracking_diagnostic(
            video,
            poses,
            tmp_path / "wrong-video",
            CrownTrackingDiagnosticConfig(),
            seed_file=seed_file,
        )
    assert not (tmp_path / "wrong-video").exists()
    with pytest.raises(ValueError, match="outside"):
        run_head_tracking_diagnostic(
            video, poses, source / "unsafe", CrownTrackingDiagnosticConfig()
        )
    with pytest.raises(FileExistsError):
        run_head_tracking_diagnostic(video, poses, output, CrownTrackingDiagnosticConfig())


def test_annotation_page_requires_explicit_bound_point_and_only_writes_diagnostic_sidecar(tmp_path):
    from fastapi.testclient import TestClient

    from golf_sim.diagnostics.crown_annotation import create_crown_annotation_app

    source = tmp_path / "source"
    source.mkdir()
    video = source / "camera_1.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 60, (220, 180))
    writer.write(cv2.cvtColor(_texture(), cv2.COLOR_GRAY2BGR))
    writer.release()
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    diagnostic = tmp_path / "diagnostic"
    diagnostic.mkdir()
    (diagnostic / "diagnostic_manifest.json").write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "test": "still",
                        "original_sha256": {"camera_1.mp4": digest},
                        "cameras": [{"role": "camera_1", "directory": str(source)}],
                    }
                ]
            }
        )
    )
    before = video.read_bytes()
    client = TestClient(create_crown_annotation_app(diagnostic))
    assert client.get("/").status_code == 200
    assert b"Crown Tracking Playback" in client.get("/?mode=playback").content
    assert client.get("/api/cases").json()["annotations"] == []
    assert client.get("/api/frame/still-camera_1/0").headers["content-type"] == "image/png"
    assert client.get("/api/frame/still-camera_1/1").status_code == 422
    assert client.get("/api/frame/unknown/0").status_code == 404
    seed = {
        "case_id": "still-camera_1",
        "camera": "camera_1",
        "video_sha256": digest,
        "frame_index": 0,
        "native_width": 220,
        "native_height": 180,
        "x": 90,
        "y": 70,
        "confirmed_visible": True,
        "origin": "operator_click",
    }
    assert client.post("/api/seeds", json={**seed, "confirmed_visible": False}).status_code == 422
    assert client.post("/api/seeds", json={**seed, "x": 220}).status_code == 422
    assert client.post("/api/seeds", json={**seed, "video_sha256": "0" * 64}).status_code == 422
    assert (
        client.post("/api/seeds", json=seed, headers={"Origin": "https://example.com"}).status_code
        == 403
    )
    assert not (diagnostic / "operator_crown_seeds.json").exists()
    assert client.post("/api/seeds", json=seed).status_code == 200
    assert client.get("/api/cases").json()["annotations"] == [seed]
    assert json.loads((diagnostic / "operator_crown_seeds.json").read_text())["annotations"] == [
        seed
    ]
    assert video.read_bytes() == before


def test_blind_validation_cannot_reveal_early_revise_or_become_tracking_seeds(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient

    import golf_sim.diagnostics.crown_annotation as annotation_module

    source = tmp_path / "source"
    source.mkdir()
    root = tmp_path / "diagnostic"
    root.mkdir()
    cases = {}
    for camera in ("camera_1", "camera_2"):
        video = source / f"{camera}.mp4"
        video.write_bytes(camera.encode())
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        case_id = f"swing-{camera}"
        cases[case_id] = {
            "case_id": case_id,
            "label": case_id,
            "camera": camera,
            "video": video,
            "video_sha256": digest,
            "native_width": 32,
            "native_height": 32,
            "frame_count": 180,
            "fps": 120,
        }
        path = root / "crown-experiment-operator-v2" / case_id / "comparison.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "summary": {
                        "source_sha256": {str(video): digest},
                        "tracking_policy": "operator_seed_independent_image_motion",
                        "operator_seed_frames": [0],
                    },
                    "frames": [
                        {
                            "frame_index": frame,
                            "candidate_xy": [13, 14],
                            "status": "image_consistent",
                        }
                        for frame in (80, 137, 177)
                    ],
                }
            )
        )
        path.with_name("comparison.mp4").write_bytes(b"synthetic comparison video bytes")
    monkeypatch.setattr(annotation_module, "_cases", lambda path: cases)
    seed_file = root / "operator_crown_seeds.json"
    seed_file.write_text(OperatorCrownSeeds().model_dump_json())
    before_seed = seed_file.read_bytes()
    client = TestClient(annotation_module.create_crown_annotation_app(root))
    listing = client.get("/api/checks").json()
    assert len(listing["cases"]) == 6
    assert "candidate_xy" not in json.dumps(listing)
    assert all(case["locked"] for case in client.get("/api/playback").json()["cases"])
    assert client.get("/api/playback/swing-camera_1").status_code == 403
    assert client.get("/api/playback/unknown").status_code == 404
    assert client.get("/api/checks/result/swing-camera_1/80").status_code == 403
    case = listing["cases"][0]
    point = {
        key: case[key]
        for key in (
            "case_id",
            "camera",
            "video_sha256",
            "frame_index",
            "native_width",
            "native_height",
            "comparison_sha256",
        )
    }
    point.update(
        x=10, y=10, confirmed_visible=True, origin="operator_click", purpose="validation_only"
    )
    assert client.post("/api/seeds", json=point).status_code == 422
    assert client.post("/api/checks", json={**point, "confirmed_visible": False}).status_code == 422
    assert client.post("/api/checks", json={**point, "frame_index": 79}).status_code == 422
    assert (
        client.post("/api/checks", json={**point, "comparison_sha256": "0" * 64}).status_code == 409
    )
    assert not (root / "operator_crown_checks.json").exists()
    response = client.post("/api/checks", json=point)
    assert response.status_code == 200
    assert response.json()["distance_px"] == 5
    assert response.json()["candidate_xy"] == [13, 14]
    assert response.json()["eligible_for_metrics"] is False
    assert client.get("/api/checks/result/swing-camera_1/80").json()["distance_px"] == 5
    saved = (root / "operator_crown_checks.json").read_bytes()
    assert client.post("/api/checks", json={**point, "x": 13}).status_code == 409
    assert (root / "operator_crown_checks.json").read_bytes() == saved
    assert seed_file.read_bytes() == before_seed
    for frame in (137, 177):
        assert client.post("/api/checks", json={**point, "frame_index": frame}).status_code == 200
    stored_checks = (root / "operator_crown_checks.json").read_bytes()
    playback = client.get("/api/playback").json()
    assert playback["eligible_for_metrics"] is False
    assert (
        next(case for case in playback["cases"] if case["case_id"] == "swing-camera_1")["locked"]
        is False
    )
    assert (
        next(case for case in playback["cases"] if case["case_id"] == "swing-camera_2")["locked"]
        is True
    )
    streamed = client.get("/api/playback/swing-camera_1", headers={"Range": "bytes=0-7"})
    assert streamed.status_code == 206
    assert streamed.content == b"syntheti"
    assert streamed.headers["content-type"] == "video/mp4"
    assert (root / "operator_crown_checks.json").read_bytes() == stored_checks
    assert seed_file.read_bytes() == before_seed
    with pytest.raises(ValueError):
        OperatorCrownSeeds.model_validate_json(saved)
    comparison_path = root / "crown-experiment-operator-v2/swing-camera_1/comparison.json"
    payload = json.loads(comparison_path.read_text())
    payload["summary"]["operator_seed_frames"].append(80)
    comparison_path.write_text(json.dumps(payload))
    assert client.get("/api/checks").status_code == 409
    assert client.get("/api/checks/result/swing-camera_1/80").status_code == 409
