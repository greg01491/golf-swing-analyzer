import json

import pytest
import yaml
from fastapi.testclient import TestClient

from golf_sim.api.runtime import CaptureRuntime
from golf_sim.api.server import create_app
from golf_sim.audio.source import SyntheticAudioSource
from golf_sim.capture.source import SyntheticCameraSource
from golf_sim.config import Config, load_config


@pytest.fixture
def config(tmp_path) -> Config:
    raw = yaml.safe_load(load_config().model_dump_json())  # start from real config shape
    raw["storage"]["data_dir"] = str(tmp_path / "data")
    raw["storage"]["db_file"] = str(tmp_path / "data" / "sessions.db")
    raw["audio_trigger"]["pre_capture_delay_s"] = 0.1
    raw["audio_trigger"]["capture_duration_s"] = 0.2
    raw["cameras"]["buffer_margin_s"] = 0.1
    for dev in raw["cameras"]["devices"]:
        dev["width"], dev["height"], dev["fps"] = 8, 6, 30
    return Config.model_validate(raw)


@pytest.fixture
def client(tmp_path, config) -> TestClient:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(json.loads(config.model_dump_json())))
    runtime = CaptureRuntime(
        config,
        camera_sources={
            dev.role: SyntheticCameraSource(fps=dev.fps, width=dev.width, height=dev.height)
            for dev in config.cameras.devices
        },
        audio_source=SyntheticAudioSource(amplitudes=[0.001] * 2000),
    )
    app = create_app(config=config, runtime=runtime, config_path=config_path)
    with TestClient(app) as test_client:
        yield test_client
    runtime.stop()


def _fake_session(config, session_id="20260101T000000Z-test0001", with_metrics=True):
    session_dir = __import__("pathlib").Path(config.storage.data_dir) / "sessions" / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "camera_1.mp4").write_bytes(b"fake")
    (session_dir / "camera_2.mp4").write_bytes(b"fake")
    (session_dir / "metadata.json").write_text(
        json.dumps({"session_id": session_id, "created_at": "2026-01-01T00:00:00+00:00"})
    )
    if with_metrics:
        (session_dir / "metrics.json").write_text(json.dumps({"metrics": [], "tips": []}))
    return session_dir


def test_sessions_empty(client):
    assert client.get("/api/sessions").json() == []


def test_sessions_listing_and_detail(client, config):
    _fake_session(config)

    listing = client.get("/api/sessions").json()
    assert len(listing) == 1
    assert listing[0]["id"] == "20260101T000000Z-test0001"
    assert listing[0]["cameras"] == ["camera_1", "camera_2"]
    assert listing[0]["has_metrics"] is True

    detail = client.get("/api/sessions/20260101T000000Z-test0001").json()
    assert detail["metadata"]["created_at"] == "2026-01-01T00:00:00+00:00"
    assert detail["metrics"] == {"metrics": [], "tips": []}


def test_session_404(client):
    assert client.get("/api/sessions/nope").status_code == 404


def test_video_serving_and_traversal_guard(client, config):
    _fake_session(config)
    ok = client.get("/api/sessions/20260101T000000Z-test0001/video/camera_1")
    assert ok.status_code == 200
    assert ok.content == b"fake"

    bad = client.get("/api/sessions/20260101T000000Z-test0001/video/..%2Fmetadata")
    assert bad.status_code == 404


def test_config_roundtrip_and_validation(client, tmp_path):
    current = client.get("/api/config").json()
    assert "audio_trigger" in current

    # a comment planted in the on-disk file must survive a UI save
    config_file = tmp_path / "config.yaml"
    config_file.write_text("# precious comment\n" + config_file.read_text())

    current["audio_trigger"]["threshold_db"] = -25.0
    assert client.put("/api/config", json=current).status_code == 200
    assert client.get("/api/config").json()["audio_trigger"]["threshold_db"] == -25.0
    assert "# precious comment" in config_file.read_text()

    invalid = {"audio_trigger": {"nonsense": True}}
    assert client.put("/api/config", json=invalid).status_code == 422


def test_capture_arm_disarm_and_manual_trigger(client):
    status = client.get("/api/capture/status").json()
    assert status["running"] is False and status["armed"] is False

    assert client.post("/api/capture/arm").json() == {"armed": True}
    assert client.get("/api/capture/status").json()["armed"] is True

    assert client.post("/api/capture/disarm").json() == {"armed": False}
    assert client.get("/api/capture/status").json()["armed"] is False

    import time

    client.post("/api/capture/trigger")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = client.get("/api/capture/status").json()
        if status["last_session"] or status["last_error"]:
            break
        time.sleep(0.05)
    assert status["last_error"] is None
    assert status["last_session"] is not None

    sessions = client.get("/api/sessions").json()
    assert any(s["id"] == status["last_session"] for s in sessions)
