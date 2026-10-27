"""FastAPI app connecting the Electron/React frontend to the backend
(spec.md IPC/API layer). Run with:

    python -m golf_sim.api.server
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from time import time_ns
from typing import Literal

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from ruamel.yaml import YAML

from golf_sim.api.runtime import CaptureRuntime
from golf_sim.api.sessions import (
    delete_all_session_media,
    delete_session_media,
    list_sessions,
    save_session_review_annotations,
    session_detail,
    session_dir_for,
    session_keypoint,
    session_landmarks,
    session_review_annotations,
    sessions_stats,
    set_session_meta,
)
from golf_sim.config import (
    CLUB_LABELS,
    CURRENT_METRIC_RANGE_DEFINITION_VERSION,
    DEFAULT_CONFIG_PATH,
    Club,
    Config,
    load_config,
    resolve_state_path,
    shipped_config_path,
)

logger = logging.getLogger(__name__)


class ClubSelection(BaseModel):
    club: Club


class MetricRangeMigrationRequest(BaseModel):
    action: Literal["accept_existing", "restore_defaults"]


class MarkerReviewAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera: Literal["camera_1", "camera_2"]
    frame_index: int = Field(ge=0)
    marker: str = Field(min_length=1, max_length=64)
    label: Literal["correct", "occluded", "mislocalized", "uncertain"]
    note: str | None = Field(default=None, max_length=2000)


class MetricReviewAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str = Field(min_length=1, max_length=64)
    definition_id: str = Field(min_length=1, max_length=128)
    label: Literal["correct", "incorrect", "uncertain"]
    expected_value: float | None = Field(default=None, allow_inf_nan=False)
    unit: str | None = Field(default=None, max_length=32)
    note: str | None = Field(default=None, max_length=2000)


class SessionReviewAnnotations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    marker_annotations: list[MarkerReviewAnnotation] = Field(default_factory=list)
    metric_annotations: list[MetricReviewAnnotation] = Field(default_factory=list)

    @model_validator(mode="after")
    def annotations_are_unique(self):
        marker_keys = [
            (item.camera, item.frame_index, item.marker) for item in self.marker_annotations
        ]
        if len(marker_keys) != len(set(marker_keys)):
            raise ValueError("marker annotations must be unique per camera/frame/marker")
        metric_keys = [(item.metric, item.definition_id) for item in self.metric_annotations]
        if len(metric_keys) != len(set(metric_keys)):
            raise ValueError("metric annotations must be unique per metric definition")
        return self


class ReviewMarkerExclusion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera: Literal["camera_1", "camera_2"]
    frame_index: int = Field(ge=0)
    marker: str = Field(min_length=1, max_length=64)


class ReviewWhatIfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exclusions: list[ReviewMarkerExclusion] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def exclusions_are_unique(self):
        keys = [(item.camera, item.frame_index, item.marker) for item in self.exclusions]
        if len(keys) != len(set(keys)):
            raise ValueError("what-if exclusions must be unique per camera/frame/marker")
        return self


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


def _run_full_pipeline(session_dir: Path, config: Config) -> Callable[[], None] | None:
    """Run analysis and return optional media work that can finish afterward."""
    from golf_sim.analysis.cli import analyze_session
    from golf_sim.capture.transcode import ensure_h264
    from golf_sim.pose.estimate import run_pose_estimation
    from golf_sim.pose.reconstruct import run_reconstruction

    pose_result = run_pose_estimation(session_dir, config.pose, transcode_overlays=False)
    pending_overlays = []
    for video in pose_result.overlay_videos:
        pending = video.with_name(f".pending_{video.name}")
        os.replace(video, pending)
        pending_overlays.append((pending, video))

    run_reconstruction(session_dir, config)
    analyze_session(session_dir, config)

    if not pending_overlays:
        return None

    def finalize_overlays() -> None:
        for pending, video in pending_overlays:
            if ensure_h264(pending):
                os.replace(pending, video)

    return finalize_overlays


def _describe(exc: Exception) -> str:
    """Human-readable text for an exception.

    Some exceptions stringify to "" -- notably AssertionError, which reached
    the UI as a bare "failed to arm: " and told the user nothing.
    """
    message = str(exc).strip() or exc.__class__.__name__
    normalized = message.casefold()
    if any(
        phrase in normalized
        for phrase in (
            "insufficient memory",
            "out of memory",
            "paging file is too small",
            "cannot allocate memory",
            "winerror 1455",
        )
    ):
        return (
            "Pose processing ran out of memory. The app now uses sequential camera inference; "
            "close memory-heavy applications and reduce camera resolution or FPS if this repeats. "
            f"System detail: {message}"
        )
    return message


def apply_env_overrides(config: Config) -> Config:
    """Re-point storage/calibration at the per-user directories the desktop
    launcher owns.

    The packaged app installs read-only (Program Files when installed for all
    users), so the relative paths in config.yaml must never win: resolved
    against the frozen bundle they land inside the install directory and every
    write fails with PermissionError. Electron passes writable per-user
    directories via these env vars.

    This must be re-applied after any reload of config.yaml (see PUT
    /api/config) -- the file legitimately still holds the relative defaults, so
    validating it hands back a config that would otherwise silently revert the
    override and break capture until the next relaunch.
    """
    if data_dir := os.environ.get("GOLF_SIM_DATA_DIR"):
        config.storage.data_dir = data_dir
        config.storage.db_file = str(Path(data_dir) / "sessions.db")
    if calibration_dir := os.environ.get("GOLF_SIM_CALIBRATION_DIR"):
        config.calibration.dir = calibration_dir
    return config


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
        data_dir = resolve_state_path(data_dir)

    app = FastAPI(title="golf-sim")
    # The packaged Electron renderer runs from file:// (null origin), so it
    # needs CORS to reach this server. Permissive is acceptable here: the
    # server binds 127.0.0.1 only (config.yaml api.host) and holds no
    # secrets beyond what's already on the local machine.
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.middleware("http")
    async def log_request_failures(request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled request failure: %s %s", request.method, request.url.path)
            raise
        expected_preview_wait = response.status_code == 503 and request.url.path.startswith(
            "/api/capture/preview/"
        )
        if response.status_code >= 400 and not expected_preview_wait:
            logger.error(
                "request failed: %s %s -> %s",
                request.method,
                request.url.path,
                response.status_code,
            )
        return response

    @app.get("/api/health")
    def health():
        return {"ready": True}

    @app.get("/api/startup")
    def startup():
        from golf_sim.audio.devices import resolve_input_device
        from golf_sim.pose.calibrate import calibration_status

        messages = []
        dependency_error = None
        try:
            for module in ("Pose2Sim", "opensim", "openvino", "onnxruntime"):
                importlib.import_module(module)
            from imageio_ffmpeg import get_ffmpeg_exe

            get_ffmpeg_exe()
            pose_ready = True
        except Exception as exc:
            pose_ready = False
            dependency_error = str(exc)
        if not pose_ready:
            messages.append(f"The 3D pose engine is unavailable: {dependency_error}")

        model_root = Path(os.path.expanduser(os.environ.get("TORCH_HOME", "~/.cache/rtmlib")))
        models_ready = len(list((model_root / "hub" / "checkpoints").glob("*.onnx"))) >= 2
        if not models_ready:
            messages.append("The offline pose models are missing from this installation.")

        calibration = calibration_status(config.calibration)
        calibration_ready = calibration.exists and not calibration.broken
        if not calibration.exists:
            messages.append("Calibrate both cameras before capturing a swing.")
        elif calibration.broken:
            messages.append("The saved camera calibration is unusable; recalibrate both cameras.")

        try:
            audio_device = resolve_input_device(config.audio_trigger.device)
            audio_ready = True
        except Exception as exc:
            audio_device = None
            audio_ready = False
            messages.append(f"Microphone unavailable: {exc}")

        data_dir.mkdir(parents=True, exist_ok=True)
        return {
            "ready": pose_ready and models_ready and calibration_ready and audio_ready,
            "pose_ready": pose_ready,
            "models_ready": models_ready,
            "calibration_ready": calibration_ready,
            "audio_ready": audio_ready,
            "audio_device": audio_device,
            "messages": messages,
        }

    processing: dict[str, str] = {}  # session_id -> "running" | "done" | "error: ..."
    # Pose estimation is CPU-heavy; serialize so back-to-back captures queue
    # instead of thrashing the machine while it's also buffering cameras.
    processing_lock = threading.Lock()

    def start_processing(
        session_dir: Path, analysis_only: bool = False, reconstruct_bundle: str | None = None
    ) -> None:
        session_id = session_dir.name
        if processing.get(session_id) == "running":
            return

        def run() -> None:
            with processing_lock:
                try:
                    if reconstruct_bundle is not None:
                        from golf_sim.analysis.cli import analyze_session
                        from golf_sim.pose.reconstruct import run_reconstruction
                        from golf_sim.pose.reconstruction_evidence import (
                            prepare_explicit_reconstruction,
                        )

                        prepare_explicit_reconstruction(session_dir, config, reconstruct_bundle)
                        run_reconstruction(session_dir, config)
                        analyze_session(session_dir, config)
                        finalize = None
                    elif analysis_only:
                        from golf_sim.analysis.cli import analyze_session

                        analyze_session(session_dir, config)
                        finalize = None
                    else:
                        finalize = processor(session_dir, config)
                    processing[session_id] = "done"
                    if finalize is not None:
                        try:
                            finalize()
                        except Exception:
                            # Metrics are already complete; optional overlay
                            # finalization must not turn a successful analysis
                            # into an error.
                            logger.exception("post-processing failed for session %s", session_id)
                except Exception as exc:
                    processing[session_id] = f"error: {_describe(exc)}"
                    logger.exception("processing failed for session %s", session_id)

        processing[session_id] = "running"
        threading.Thread(target=run, daemon=True, name=f"process-{session_id}").start()

    if config.processing.auto_process:
        runtime.on_session = start_processing

    @app.get("/api/sessions")
    def get_sessions():
        return list_sessions(data_dir)

    @app.get("/api/stats")
    def get_stats():
        return sessions_stats(data_dir)

    @app.get("/api/clubs")
    def get_clubs():
        return [{"id": club, "label": label} for club, label in CLUB_LABELS.items()]

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str):
        try:
            return session_detail(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/sessions/{session_id}/keypoint/{camera}/{frame_index}/{marker}")
    def get_session_keypoint(session_id: str, camera: str, frame_index: int, marker: str):
        try:
            keypoint = session_keypoint(data_dir, session_id, camera, frame_index, marker)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if keypoint is None:
            raise HTTPException(404, "2D marker coordinate is unavailable for this frame")
        return keypoint

    @app.get("/api/sessions/{session_id}/review")
    def get_session_review(session_id: str):
        try:
            annotations = session_review_annotations(data_dir, session_id)
            return SessionReviewAnnotations.model_validate(annotations).model_dump(mode="json")
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, f"saved review annotations are invalid: {exc}") from exc

    @app.get("/api/sessions/{session_id}/review/issues")
    def get_session_review_issues(session_id: str):
        from golf_sim.analysis.cli import session_review_issues

        try:
            directory = session_dir_for(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        try:
            return session_review_issues(directory, config)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(409, f"review evidence unavailable: {exc}") from exc

    @app.put("/api/sessions/{session_id}/review")
    def put_session_review(session_id: str, annotations: SessionReviewAnnotations):
        payload = annotations.model_dump(mode="json")
        try:
            save_session_review_annotations(data_dir, session_id, payload)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        return payload

    @app.post("/api/sessions/{session_id}/review/what-if")
    def session_review_what_if(session_id: str, request: ReviewWhatIfRequest):
        from golf_sim.analysis.cli import analyze_session_what_if

        try:
            session_dir_for(data_dir, session_id)
            saved = SessionReviewAnnotations.model_validate(
                session_review_annotations(data_dir, session_id)
            )
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, f"saved review annotations are invalid: {exc}") from exc

        reviewed = {
            (item.camera, item.frame_index, item.marker) for item in saved.marker_annotations
        }
        requested = {(item.camera, item.frame_index, item.marker) for item in request.exclusions}
        if not requested <= reviewed:
            raise HTTPException(422, "what-if exclusions must reference saved marker annotations")

        try:
            return analyze_session_what_if(
                session_dir_for(data_dir, session_id),
                config,
                [item.model_dump() for item in request.exclusions],
            )
        except FileNotFoundError as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, f"what-if analysis unavailable: {exc}") from exc

    @app.patch("/api/sessions/{session_id}")
    def patch_session(session_id: str, patch: dict):
        # move a swing into a group ("My Swings"/"Professional Swings") and/or
        # rename it (e.g. "Rory McIlroy Iron Swing"); only provided keys change
        group = patch.get("group")
        label = patch.get("label")
        if group is not None and not isinstance(group, str):
            raise HTTPException(422, "group must be a string")
        if label is not None and not isinstance(label, str):
            raise HTTPException(422, "label must be a string")
        try:
            return set_session_meta(data_dir, session_id, group=group, label=label)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.delete("/api/sessions/media")
    def delete_all_media():
        return delete_all_session_media(data_dir)

    @app.delete("/api/sessions/{session_id}/media")
    def delete_media(session_id: str):
        try:
            return delete_session_media(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/sessions/{session_id}/video/{camera}")
    def get_video(session_id: str, camera: str, overlay: bool = False):
        try:
            session_dir = session_dir_for(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        if Path(camera).name != camera:
            raise HTTPException(404, "invalid camera name")
        # overlay=true serves the pose-estimation debug video (skeleton drawn
        # on the golfer) instead of the raw clip; produced during processing
        # when pose.save_debug_video is on
        video = (
            session_dir / "pose2sim" / "pose" / f"{camera}_pose.mp4"
            if overlay
            else session_dir / f"{camera}.mp4"
        )
        if not video.exists():
            raise HTTPException(404, f"no {'overlay ' if overlay else ''}clip {camera}")
        # no-cache = revalidate (ETag/mtime) before reuse, not "don't cache":
        # clips can be replaced in place (H.264 migration, overlay rewrites
        # after reprocessing), and Chromium's media cache otherwise kept
        # serving a stale pre-transcode copy that no longer decoded
        return FileResponse(video, media_type="video/mp4", headers={"Cache-Control": "no-cache"})

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

    @app.post("/api/sessions/{session_id}/reconstruct")
    def reconstruct_session(session_id: str, body: dict):
        from golf_sim.pose.calibration_bundle import (
            camera_signatures,
            compare_signatures,
            load_active_bundle,
        )
        from golf_sim.pose.project import landmark_json_dirs

        try:
            directory = session_dir_for(data_dir, session_id)
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        bundle = load_active_bundle(resolve_state_path(config.calibration.dir))
        if bundle is None or body.get("bundle_id") != bundle["bundle_id"]:
            raise HTTPException(409, "explicit selection of the accepted active bundle is required")
        metadata = json.loads((directory / "metadata.json").read_text())
        compatibility = compare_signatures(
            bundle["signatures"], camera_signatures(config, metadata)
        )
        if compatibility["status"] != "compatible":
            raise HTTPException(
                409,
                "saved capture compatibility is not established: "
                + "; ".join(compatibility["reasons"]),
            )
        if not landmark_json_dirs(directory / "pose2sim"):
            raise HTTPException(
                409, "saved 2D pose observations are missing; full processing is required"
            )
        start_processing(directory, reconstruct_bundle=bundle["bundle_id"])
        return {"status": processing.get(session_id, "running")}

    @app.get("/api/sessions/{session_id}/process")
    def process_status(session_id: str):
        return {"status": processing.get(session_id, "idle")}

    @app.post("/api/sessions/{session_id}/reanalyze")
    def reanalyze_session(session_id: str):
        from golf_sim.analysis.cli import pick_trc

        try:
            session_dir = session_dir_for(data_dir, session_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
        try:
            pick_trc(session_dir)
        except FileNotFoundError as exc:
            raise HTTPException(
                409, "saved 3D landmarks are unavailable; reprocess the swing first"
            ) from exc
        start_processing(session_dir, analysis_only=True)
        return {"status": processing.get(session_id, "running")}

    @app.get("/api/config")
    def get_config():
        return yaml.safe_load(Path(config_path).read_text())

    @app.get("/api/config/metric-ranges/status")
    def get_metric_range_status():
        raw = yaml.safe_load(Path(config_path).read_text()) or {}
        metrics = raw.get("metrics") or {}
        configured_version = metrics.get("range_definition_version")
        if configured_version == CURRENT_METRIC_RANGE_DEFINITION_VERSION:
            status = "current"
        elif configured_version is None:
            status = "legacy"
        else:
            status = "unsupported"
        return {
            "status": status,
            "configured_version": configured_version,
            "current_version": CURRENT_METRIC_RANGE_DEFINITION_VERSION,
            "reference_range_count": len(metrics.get("reference_ranges") or {}),
            "club_profile_count": len(metrics.get("club_profiles") or {}),
        }

    @app.post("/api/config/metric-ranges/migrate")
    def migrate_metric_ranges(request: MetricRangeMigrationRequest):
        nonlocal config
        path = Path(config_path)
        original = path.read_bytes()
        raw = yaml.safe_load(original) or {}
        metrics = raw.get("metrics")
        if not isinstance(metrics, dict):
            raise HTTPException(422, "configuration has no valid metrics section")
        if metrics.get("range_definition_version") == CURRENT_METRIC_RANGE_DEFINITION_VERSION:
            raise HTTPException(409, "metric ranges already use the current definition")

        if request.action == "restore_defaults":
            default_metrics = load_config(shipped_config_path()).metrics
            metrics["reference_ranges"] = {
                name: value.model_dump() for name, value in default_metrics.reference_ranges.items()
            }
            metrics["club_profiles"] = {
                profile: {name: value.model_dump() for name, value in ranges.items()}
                for profile, ranges in default_metrics.club_profiles.items()
            }
            metrics["club_profile_mapping"] = default_metrics.club_profile_mapping
        metrics["range_definition_version"] = CURRENT_METRIC_RANGE_DEFINITION_VERSION
        try:
            validated = Config.model_validate(raw)
        except Exception as exc:
            raise HTTPException(422, f"invalid config after metric range migration: {exc}") from exc

        backup_file = f"{path.name}.before-metric-range-migration-{time_ns()}.bak"
        backup_path = path.with_name(backup_file)
        backup_path.write_bytes(original)
        try:
            _write_config_preserving_comments(path, {"metrics": metrics})
            validated = apply_env_overrides(validated)
        except Exception:
            path.write_bytes(original)
            raise

        runtime.config = validated
        config = validated
        return {
            "status": "migrated",
            "action": request.action,
            "current_version": CURRENT_METRIC_RANGE_DEFINITION_VERSION,
            "backup_file": backup_file,
        }

    @app.put("/api/config")
    def put_config(new_config: dict):
        nonlocal config
        # validate before persisting so a bad edit can't brick the app
        try:
            validated = Config.model_validate(new_config)
        except Exception as exc:
            raise HTTPException(422, f"invalid config: {exc}") from exc
        preview_only = runtime.running and not runtime.armed
        _write_config_preserving_comments(Path(config_path), new_config)
        # config.yaml still stores the relative default paths, so re-apply the
        # launcher's per-user directory overrides here. Without this a settings
        # save silently repointed storage back inside the (read-only) install
        # directory and every later capture failed with PermissionError.
        validated = apply_env_overrides(validated)
        # keep the live runtime's config in sync so disarm/arm (which now
        # fully tears down and rebuilds CaptureService) actually picks up the
        # change -- previously this was never updated, so the "disarm/arm to
        # apply" note below was a lie and only a full app relaunch worked.
        runtime.config = validated
        config = validated
        if preview_only:
            runtime.stop()
            runtime.start_cameras()
            return {"status": "saved", "note": "camera preview restarted with the new settings"}
        return {"status": "saved", "note": "restart capture (disarm/arm) to apply"}

    @app.get("/api/capture/preview/{camera}")
    def capture_preview(camera: str):
        import cv2
        from fastapi.responses import Response

        image = runtime.latest_frame(camera)
        if image is None:
            raise HTTPException(503, "camera not running -- arm capture first")
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ok:
            raise HTTPException(500, "encode failed")
        return Response(
            content=jpeg.tobytes(),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    calib_compute: dict = {"state": "idle"}

    @app.post("/api/capture/preview/start")
    @app.post("/api/calibration/preview/start")
    def calibration_preview_start():
        try:
            runtime.start_cameras()
        except Exception as exc:
            logger.exception("calibration camera startup failed")
            raise HTTPException(500, f"camera startup failed: {exc}") from exc
        return {"running": True}

    @app.post("/api/calibration/preview/stop")
    def calibration_preview_stop():
        runtime.stop()
        return {"running": False}

    @app.post("/api/calibration/shot")
    def calibration_shot(body: dict):
        from golf_sim.pose.wizard import mark_calibration_shot

        kind = body.get("kind")
        if kind not in ("intrinsics", "extrinsics", "ground"):
            raise HTTPException(422, "kind must be 'intrinsics', 'extrinsics' or 'ground'")
        if kind == "ground":
            from golf_sim.pose.calibration_bundle import load_active_bundle

            if body.get("level_confirmed") is not True or body.get("target_confirmed") is not True:
                raise HTTPException(
                    422, "confirm the board is level and its marked target edge is aligned"
                )
            if load_active_bundle(resolve_state_path(config.calibration.dir)) is None:
                raise HTTPException(409, "accept camera geometry before ground-reference capture")
        for_camera = body.get("camera")
        valid_roles = {dev.role for dev in config.cameras.devices}
        if for_camera is not None and for_camera not in valid_roles:
            raise HTTPException(422, f"camera must be one of {sorted(valid_roles)}")
        logger.info("calibration capture starting: kind=%s camera=%s", kind, for_camera)
        try:
            session_dir = runtime.capture_calibration_shot()
        except Exception as exc:
            logger.exception("calibration capture failed")
            raise HTTPException(500, f"capture failed: {exc}") from exc
        try:
            marker = mark_calibration_shot(
                session_dir, kind, config, for_camera=for_camera, ground_confirmations=body
            )
        except Exception:
            logger.exception("calibration board analysis failed for %s", session_dir.name)
            raise
        logger.info(
            "calibration capture saved: id=%s kind=%s camera=%s board_frames=%s",
            session_dir.name,
            kind,
            for_camera,
            marker["board_frames_detected"],
        )
        return {"id": session_dir.name, **marker}

    @app.get("/api/calibration/shots")
    def calibration_shots():
        from golf_sim.pose.wizard import list_calibration_shots

        return list_calibration_shots(data_dir)

    @app.delete("/api/calibration/shots")
    def calibration_shots_clear():
        from golf_sim.pose.wizard import clear_calibration_shots

        return {"deleted": clear_calibration_shots(data_dir)}

    calib_cancelled = threading.Event()
    calibration_job = threading.Lock()

    @app.post("/api/calibration/compute")
    def calibration_compute(body: dict):
        from golf_sim.pose.wizard import compute_rig_calibration

        distance = body.get("camera_distance_m")
        if not isinstance(distance, (int, float)) or not 0.3 < distance < 20:
            raise HTTPException(422, "camera_distance_m must be a number in metres (0.3-20)")
        if not calibration_job.acquire(blocking=False):
            return calib_compute

        def run() -> None:
            try:
                result = compute_rig_calibration(
                    data_dir,
                    config,
                    float(distance),
                    on_stage=lambda msg: calib_compute.update(stage=msg),
                    cancelled=calib_cancelled.is_set,
                )
                calib_compute.update(state="done", result=result)
            except Exception as exc:
                calib_compute.update(state="error", error=str(exc))
                if getattr(exc, "validation_report", None) is not None:
                    calib_compute["validation"] = exc.validation_report
                from golf_sim.pose.calibration_bundle import atomic_json

                try:
                    atomic_json(
                        resolve_state_path(config.calibration.dir) / "last-candidate.json",
                        {
                            "status": "failed",
                            "error": str(exc),
                            "validation": getattr(exc, "validation_report", None),
                            "stage": calib_compute.get("stage"),
                        },
                    )
                except OSError:
                    logger.exception("could not retain failed candidate report")
                logger.exception("calibration computation failed")
            finally:
                calibration_job.release()

        calib_compute.clear()
        calib_cancelled.clear()
        calib_compute.update(state="running", stage="starting")
        threading.Thread(target=run, daemon=True, name="rig-calibration").start()
        return calib_compute

    @app.get("/api/calibration/compute")
    def calibration_compute_status():
        return calib_compute

    @app.delete("/api/calibration/compute")
    def calibration_compute_cancel():
        from golf_sim.pose.calibration_bundle import activation_guard

        with activation_guard():
            if (
                calib_compute["state"] == "running"
                and calib_compute.get("stage") != "camera calibration accepted"
            ):
                calib_cancelled.set()
        return calib_compute

    ground_compute: dict = {"state": "idle"}
    ground_cancelled = threading.Event()
    ground_job = threading.Lock()

    @app.post("/api/calibration/ground")
    def ground_reference_compute(body: dict):
        from golf_sim.pose.ground_reference import compute_ground_reference

        session_ids = body.get("session_ids")
        origins = body.get("origins")
        side = body.get("golfer_side")
        if (
            not isinstance(session_ids, list)
            or not all(
                isinstance(identity, str) and Path(identity).name == identity
                for identity in session_ids
            )
            or len(set(session_ids)) < 2
            or not isinstance(origins, dict)
            or isinstance(side, bool)
            or side not in (-1, 1)
        ):
            raise HTTPException(
                422,
                "two reference captures, per-camera marked origins and golfer side are required",
            )
        if not ground_job.acquire(blocking=False):
            return ground_compute

        def solve() -> None:
            try:
                result = compute_ground_reference(
                    data_dir, config, session_ids, origins, side, cancelled=ground_cancelled.is_set
                )
                ground_compute.update(state="done", result=result)
            except Exception as error:
                ground_compute.update(state="error", error=str(error))
                logger.exception("ground reference validation failed")
            finally:
                ground_job.release()

        ground_compute.clear()
        ground_cancelled.clear()
        ground_compute.update(state="running")
        threading.Thread(target=solve, daemon=True, name="ground-reference").start()
        return ground_compute

    @app.get("/api/calibration/ground")
    def ground_reference_status():
        return ground_compute

    @app.delete("/api/calibration/ground")
    def ground_reference_cancel():
        from golf_sim.pose.calibration_bundle import activation_guard

        with activation_guard():
            if ground_compute["state"] == "running":
                ground_cancelled.set()
        return ground_compute

    @app.get("/api/calibration/shots/{session_id}/ground-preview/{camera}")
    def ground_reference_preview(session_id: str, camera: str):
        if camera not in ("camera_1", "camera_2"):
            raise HTTPException(404, "unknown camera role")
        try:
            directory = session_dir_for(data_dir, session_id)
        except FileNotFoundError as error:
            raise HTTPException(404, str(error)) from error
        image = directory / f"ground-preview-{camera}.jpg"
        if not image.exists():
            raise HTTPException(404, "board preview unavailable; recapture with visible corners")
        return FileResponse(image, media_type="image/jpeg")

    @app.get("/api/calibration/info")
    def calibration_info():
        from golf_sim.pose.calibrate import calibration_status, last_candidate_report

        status = calibration_status(config.calibration)
        from golf_sim.pose.calibration_bundle import (
            camera_signatures,
            compare_signatures,
            load_active_bundle,
        )

        try:
            bundle = load_active_bundle(resolve_state_path(config.calibration.dir))
        except (OSError, ValueError, KeyError):
            bundle = None
        compatibility = (
            compare_signatures(bundle["signatures"], camera_signatures(config))
            if bundle
            else {"status": "legacy-unverified", "reasons": ["capture evidence is unavailable"]}
        )
        return {
            "exists": status.exists,
            "file": str(status.file) if status.file else None,
            "age_days": status.age_days,
            "stale": status.stale,
            "reprojection_error_px": status.reprojection_error_px,
            "broken": status.broken,
            "validation_status": status.validation_status,
            "validation": status.validation,
            "bundle_id": status.bundle_id,
            "ground_status": status.ground_status,
            "compatibility": compatibility,
            "reasons": status.reasons or [],
            "last_candidate": last_candidate_report(config.calibration),
        }

    @app.get("/api/calibration/board.png")
    def calibration_board():
        from fastapi.responses import Response

        from golf_sim.pose.board_image import generate_board_png

        png = generate_board_png(tuple(config.calibration.checkerboard_corners))
        return Response(content=png, media_type="image/png")

    @app.get("/api/diagnostics/system")
    def diagnostics_system():
        from golf_sim.diagnostics.system_check import check_system

        return check_system(Path(config.storage.data_dir), config.system_requirements)

    @app.get("/api/diagnostics/cameras")
    def diagnostics_cameras():
        from golf_sim.diagnostics.camera_check import check_camera

        if runtime.running:
            raise HTTPException(
                409, "disarm capture first to run the camera check -- the cameras are in use"
            )
        return [check_camera(dev, config.system_requirements) for dev in config.cameras.devices]

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
            "selected_club": runtime.selected_club,
        }

    @app.put("/api/capture/club")
    def select_club(selection: ClubSelection):
        runtime.select_club(selection.club)
        return {"club": selection.club}

    @app.post("/api/capture/arm")
    def arm():
        try:
            runtime.arm()
        except Exception as exc:
            logger.exception("arm failed")
            raise HTTPException(500, f"failed to arm: {_describe(exc)}") from exc
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
            logger.exception("manual trigger failed")
            raise HTTPException(500, f"manual trigger failed: {_describe(exc)}") from exc
        return {"triggered": True}

    return app


def main() -> None:
    import uvicorn

    # uvicorn configures its own loggers but leaves the root logger alone, so
    # without this every golf_sim logger.info()/debug() is swallowed by
    # logging.lastResort (WARNING-only). That silently hid the calibration
    # diagnostics we rely on to debug installed builds from the log file.
    logging.basicConfig(
        level=os.environ.get("GOLF_SIM_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config_path = Path(os.environ.get("GOLF_SIM_CONFIG_PATH", DEFAULT_CONFIG_PATH))
    config = apply_env_overrides(load_config(config_path))

    # Pose2Sim's filtering module deadlocks if its qtagg/plt.figure() probe
    # first runs on a worker thread (which is how background processing runs).
    # Run it here, on the main thread, before serving -- otherwise the first
    # auto-processed capture hangs the whole server. Skipped cleanly if the
    # pose extra isn't installed (capture-only deployments) or auto-process
    # is off; run_reconstruction preloads it itself in that case.
    if config.processing.auto_process:
        try:
            from golf_sim.pose.reconstruct import preload_headless_pose_stack

            preload_headless_pose_stack()
        except Exception:
            logger.warning("pose stack preload skipped", exc_info=True)

    uvicorn.run(
        create_app(config, config_path=config_path),
        host=config.api.host,
        port=config.api.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
