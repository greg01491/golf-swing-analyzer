"""FastAPI app connecting the Electron/React frontend to the backend
(spec.md IPC/API layer). Run with:

    python -m golf_sim.api.server
"""

from __future__ import annotations

import threading
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from ruamel.yaml import YAML

from golf_sim.api.runtime import CaptureRuntime
from golf_sim.api.sessions import (
    list_sessions,
    session_detail,
    session_dir_for,
    session_landmarks,
)
from golf_sim.config import DEFAULT_CONFIG_PATH, REPO_ROOT, Config, load_config


def _deep_update(target, source: dict) -> None:
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


def _write_config_preserving_comments(config_path: Path, new_config: dict) -> None:
    """Merge new values into the existing YAML document via ruamel's
    round-trip mode, so the file's comments (which document each parameter,
    including hardware findings) survive UI edits. A plain yaml.safe_dump
    here silently destroyed them."""
    ruamel = YAML()
    ruamel.preserve_quotes = True
    if config_path.exists():
        doc = ruamel.load(config_path.read_text())
        _deep_update(doc, new_config)
    else:
        doc = new_config
    with open(config_path, "w") as f:
        ruamel.dump(doc, f)


def _run_full_pipeline(session_dir: Path, config: Config) -> None:
    """2D pose -> 3D reconstruction -> metrics + tips for one session."""
    from golf_sim.analysis.cli import analyze_session
    from golf_sim.pose.estimate import run_pose_estimation
    from golf_sim.pose.reconstruct import run_reconstruction

    run_pose_estimation(session_dir, config.pose)
    run_reconstruction(session_dir, config)
    analyze_session(session_dir, config)


def create_app(
    config: Config | None = None,
    runtime: CaptureRuntime | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    processor=None,
) -> FastAPI:
    """processor: override the per-session processing pipeline (tests inject a
    fake; None means the real pose->3D->metrics chain)."""
    config = config or load_config(config_path)
    runtime = runtime or CaptureRuntime(config)
    processor = processor or _run_full_pipeline
    data_dir = Path(config.storage.data_dir)
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir

    app = FastAPI(title="golf-sim")
    # The packaged Electron renderer runs from file:// (null origin), so it
    # needs CORS to reach this server. Permissive is acceptable here: the
    # server binds 127.0.0.1 only (config.yaml api.host) and holds no
    # secrets beyond what's already on the local machine.
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    processing: dict[str, str] = {}  # session_id -> "running" | "done" | "error: ..."
    # Pose estimation is CPU-heavy; serialize so back-to-back captures queue
    # instead of thrashing the machine while it's also buffering cameras.
    processing_lock = threading.Lock()

    def start_processing(session_dir: Path) -> None:
        session_id = session_dir.name
        if processing.get(session_id) == "running":
            return

        def run() -> None:
            with processing_lock:
                try:
                    processor(session_dir, config)
                    processing[session_id] = "done"
                except Exception as exc:
                    processing[session_id] = f"error: {exc}"

        processing[session_id] = "running"
        threading.Thread(target=run, daemon=True, name=f"process-{session_id}").start()

    if config.processing.auto_process:
        runtime.on_session = start_processing

    @app.get("/api/sessions")
    def get_sessions():
        return list_sessions(data_dir)

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        try:
            return session_detail(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/sessions/{session_id}/video/{camera}")
    def get_video(session_id: str, camera: str):
        try:
            session_dir = session_dir_for(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        if Path(camera).name != camera:
            raise HTTPException(404, "invalid camera name")
        video = session_dir / f"{camera}.mp4"
        if not video.exists():
            raise HTTPException(404, f"no clip {camera} in session {session_id}")
        return FileResponse(video, media_type="video/mp4")

    @app.get("/api/sessions/{session_id}/landmarks")
    def get_landmarks(session_id: str):
        try:
            return session_landmarks(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/sessions/{session_id}/process")
    def process_session(session_id: str):
        try:
            session_dir = session_dir_for(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        start_processing(session_dir)
        return {"status": processing.get(session_id, "running")}

    @app.get("/api/sessions/{session_id}/process")
    def process_status(session_id: str):
        return {"status": processing.get(session_id, "idle")}

    @app.get("/api/config")
    def get_config():
        return yaml.safe_load(Path(config_path).read_text())

    @app.put("/api/config")
    def put_config(new_config: dict):
        # validate before persisting so a bad edit can't brick the app
        try:
            Config.model_validate(new_config)
        except Exception as exc:
            raise HTTPException(422, f"invalid config: {exc}") from exc
        _write_config_preserving_comments(Path(config_path), new_config)
        return {"status": "saved", "note": "restart capture (disarm/arm) to apply"}

    @app.get("/api/capture/status")
    def capture_status():
        return {
            "running": runtime.running,
            "armed": runtime.armed,
            "mic_level_db": runtime.mic_level_db,
            "mic_error": runtime.mic_error,
            "camera_health": runtime.camera_health,
            "last_session": runtime.last_session_dir.name if runtime.last_session_dir else None,
            "last_error": runtime.last_error,
        }

    @app.post("/api/capture/arm")
    def arm():
        try:
            runtime.arm()
        except Exception as exc:
            raise HTTPException(500, f"failed to arm: {exc}") from exc
        return {"armed": True}

    @app.post("/api/capture/disarm")
    def disarm():
        runtime.disarm()
        return {"armed": False}

    @app.post("/api/capture/trigger")
    def trigger():
        try:
            runtime.manual_trigger()
        except Exception as exc:
            raise HTTPException(500, f"manual trigger failed: {exc}") from exc
        return {"triggered": True}

    return app


def main() -> None:
    import uvicorn

    config = load_config()
    uvicorn.run(create_app(config), host=config.api.host, port=config.api.port)


if __name__ == "__main__":
    main()
