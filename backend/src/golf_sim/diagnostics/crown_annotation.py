"""Loopback-only operator crown annotation for isolated diagnostic copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import threading
from pathlib import Path
from typing import Literal

import cv2
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from golf_sim.diagnostics.crown_tracking import OperatorCrownSeed, OperatorCrownSeeds
from golf_sim.pose.calibration_bundle import atomic_json


class CrownValidationPoint(OperatorCrownSeed):
    purpose: Literal["validation_only"]
    comparison_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CrownValidationPoints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    purpose: Literal["validation_only"]
    annotations: list[CrownValidationPoint] = Field(default_factory=list)


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _cases(root: Path) -> dict:
    manifest = json.loads((root / "diagnostic_manifest.json").read_text())
    videos = []
    for session in manifest["sessions"]:
        for camera in session["cameras"]:
            role = camera["role"]
            videos.append(
                (
                    session["test"],
                    role,
                    Path(camera["directory"]) / f"{role}.mp4",
                    session["original_sha256"][f"{role}.mp4"],
                )
            )
    swing_path = root / "crown-experiment-v1" / "original_swing_source_hashes.json"
    if swing_path.exists():
        swing = json.loads(swing_path.read_text())
        for role in ("camera_1", "camera_2"):
            videos.append(
                (
                    "swing",
                    role,
                    Path(swing["source"]) / f"{role}.mp4",
                    swing["source_sha256"][f"{role}.mp4"],
                )
            )
    cases = {}
    for label, role, video, expected in videos:
        digest = _digest(video)
        if digest != expected:
            raise ValueError(f"diagnostic source video changed: {label}/{role}")
        capture = cv2.VideoCapture(str(video), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
        try:
            if not capture.isOpened():
                raise ValueError(f"cannot read {video}")
            case_id = f"{label}-{role}"
            view = "Down-the-line" if role == "camera_1" else "Face-on"
            cases[case_id] = {
                "case_id": case_id,
                "label": f"{label.title()} / {view}",
                "camera": role,
                "video": video,
                "video_sha256": digest,
                "native_width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "native_height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
                "fps": capture.get(cv2.CAP_PROP_FPS),
            }
        finally:
            capture.release()
    return cases


def create_crown_annotation_app(root: Path) -> FastAPI:
    """Serve only known diagnostic frames; save annotations only in the diagnostic root."""
    root = Path(root).resolve()
    cases = _cases(root)
    seed_file = root / "operator_crown_seeds.json"
    check_file = root / "operator_crown_checks.json"
    lock = threading.Lock()
    app = FastAPI()

    def saved() -> OperatorCrownSeeds:
        return (
            OperatorCrownSeeds.model_validate_json(seed_file.read_text())
            if seed_file.exists()
            else OperatorCrownSeeds()
        )

    def checks() -> CrownValidationPoints:
        return (
            CrownValidationPoints.model_validate_json(check_file.read_text())
            if check_file.exists()
            else CrownValidationPoints(purpose="validation_only")
        )

    def comparison(case_id: str, *, validation: bool = True) -> tuple[dict, Path, dict, str]:
        case = cases.get(case_id)
        if case is None or (validation and case_id not in {"swing-camera_1", "swing-camera_2"}):
            raise HTTPException(404, "unknown validation case")
        path = root / "crown-experiment-operator-v2" / case_id / "comparison.json"
        if not path.exists():
            raise HTTPException(409, "fixed comparison is unavailable")
        digest = _digest(path)
        payload = json.loads(path.read_text())
        summary = payload["summary"]
        if (
            summary.get("source_sha256", {}).get(str(case["video"])) != case["video_sha256"]
            or summary.get("tracking_policy") != "operator_seed_independent_image_motion"
            or _digest(case["video"]) != case["video_sha256"]
        ):
            raise HTTPException(409, "comparison source binding is invalid")
        return case, path, payload, digest

    def validate_annotation(annotation: OperatorCrownSeed) -> dict:
        case = cases.get(annotation.case_id)
        if case is None:
            raise HTTPException(404, "unknown diagnostic case")
        if (
            annotation.camera != case["camera"]
            or annotation.video_sha256 != case["video_sha256"]
            or annotation.native_width != case["native_width"]
            or annotation.native_height != case["native_height"]
            or annotation.frame_index >= case["frame_count"]
            or annotation.x >= case["native_width"]
            or annotation.y >= case["native_height"]
        ):
            raise HTTPException(422, "annotation does not match this exact native video frame")
        if _digest(case["video"]) != case["video_sha256"]:
            raise HTTPException(409, "video changed; reload the diagnostic")
        return case

    def validate_request(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is not None and origin != str(request.base_url).rstrip("/"):
            raise HTTPException(403, "cross-origin annotations are not allowed")
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "JSON annotation required")

    def result(annotation: CrownValidationPoint) -> dict:
        _, _, payload, digest = comparison(annotation.case_id)
        if digest != annotation.comparison_sha256:
            raise HTTPException(409, "comparison changed after the independent judgment")
        frames = payload["frames"]
        record = next(
            (item for item in frames if item["frame_index"] == annotation.frame_index), None
        )
        if record is None:
            raise HTTPException(409, "comparison frame is unavailable")
        point = record["candidate_xy"]
        return {
            "candidate_xy": point,
            "distance_px": (
                None
                if point is None
                else math.hypot(point[0] - annotation.x, point[1] - annotation.y)
            ),
            "tracking_status": record["status"],
            "diagnostic_only": True,
            "eligible_for_metrics": False,
        }

    @app.get("/")
    def index(mode: str | None = None):
        name = "crown_playback.html" if mode == "playback" else "crown_annotation.html"
        return FileResponse(Path(__file__).with_name(name))

    @app.get("/api/cases")
    def get_cases():
        with lock:
            return {
                "cases": [
                    {key: value for key, value in case.items() if key != "video"}
                    for case in cases.values()
                ],
                "annotations": saved().model_dump(mode="json")["annotations"],
                "diagnostic_only": True,
            }

    def playback_case(case_id: str) -> tuple[dict, Path, dict, bool]:
        case, path, payload, digest = comparison(case_id, validation=False)
        video = path.with_name("comparison.mp4")
        if not video.is_file():
            raise HTTPException(409, "comparison video is unavailable")
        with lock:
            completed = {
                item.frame_index
                for item in checks().annotations
                if item.case_id == case_id
                and item.comparison_sha256 == digest
                and item.video_sha256 == case["video_sha256"]
            }
        locked = case_id.startswith("swing-") and not {80, 137, 177} <= completed
        return case, video, payload, locked

    @app.get("/api/playback")
    def get_playback_cases():
        views = []
        for case_id in cases:
            case, _, payload, locked = playback_case(case_id)
            summary = payload["summary"]
            views.append(
                {
                    **{key: value for key, value in case.items() if key != "video"},
                    "locked": locked,
                    "video_url": None if locked else f"/api/playback/{case_id}",
                    "image_supported_fraction": (
                        None if locked else summary.get("image_supported_fraction")
                    ),
                    "status_counts": {} if locked else summary.get("status_counts", {}),
                    "frame_statuses": (
                        [] if locked else [item["status"] for item in payload["frames"]]
                    ),
                }
            )
        return {"cases": views, "diagnostic_only": True, "eligible_for_metrics": False}

    @app.get("/api/playback/{case_id}")
    def get_playback_video(case_id: str):
        _, video, _, locked = playback_case(case_id)
        if locked:
            raise HTTPException(403, "complete this view's independent checks before playback")
        return FileResponse(video, media_type="video/mp4", headers={"Cache-Control": "no-store"})

    @app.get("/api/frame/{case_id}/{frame_index}")
    def get_frame(case_id: str, frame_index: int):
        case = cases.get(case_id)
        if case is None:
            raise HTTPException(404, "unknown diagnostic case")
        if not 0 <= frame_index < case["frame_count"]:
            raise HTTPException(422, "frame is outside the native clip")
        capture = cv2.VideoCapture(str(case["video"]), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 1])
        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, image = capture.read()
            if not ok:
                raise HTTPException(409, "native frame cannot be decoded")
            ok, encoded = cv2.imencode(".png", image)
            if not ok:
                raise HTTPException(409, "native frame cannot be encoded")
            return Response(
                encoded.tobytes(), media_type="image/png", headers={"Cache-Control": "no-store"}
            )
        finally:
            capture.release()

    @app.post("/api/seeds")
    def save_seed(annotation: OperatorCrownSeed, request: Request):
        validate_request(request)
        validate_annotation(annotation)
        with lock:
            annotations = saved()
            annotations.annotations = [
                item
                for item in annotations.annotations
                if (item.case_id, item.frame_index) != (annotation.case_id, annotation.frame_index)
            ]
            annotations.annotations.append(annotation)
            atomic_json(seed_file, annotations.model_dump(mode="json"))
        return {"saved": True, "diagnostic_only": True}

    @app.get("/api/checks")
    def get_checks():
        tasks = []
        for case_id in ("swing-camera_1", "swing-camera_2"):
            case, _, payload, digest = comparison(case_id)
            for frame in (80, 137, 177):
                if frame in payload["summary"].get("operator_seed_frames", []):
                    raise HTTPException(409, "validation frame was used as a tracking seed")
                tasks.append(
                    {
                        **{key: value for key, value in case.items() if key != "video"},
                        "frame_index": frame,
                        "comparison_sha256": digest,
                        "label": f'{case["label"]} / frame {frame}',
                    }
                )
        with lock:
            return {
                "cases": tasks,
                "annotations": checks().model_dump(mode="json")["annotations"],
                "purpose": "validation_only",
            }

    @app.post("/api/checks")
    def save_check(annotation: CrownValidationPoint, request: Request):
        validate_request(request)
        validate_annotation(annotation)
        _, _, payload, digest = comparison(annotation.case_id)
        if annotation.frame_index not in {80, 137, 177} or annotation.frame_index in payload[
            "summary"
        ].get("operator_seed_frames", []):
            raise HTTPException(422, "only held-out validation frames can be checked")
        if annotation.comparison_sha256 != digest:
            raise HTTPException(409, "comparison changed before judgment was saved")
        scored = result(annotation)
        with lock:
            saved_checks = checks()
            if any(
                (item.case_id, item.frame_index) == (annotation.case_id, annotation.frame_index)
                for item in saved_checks.annotations
            ):
                raise HTTPException(
                    409, "independent judgment is already saved and cannot be revised after reveal"
                )
            saved_checks.annotations.append(annotation)
            atomic_json(check_file, saved_checks.model_dump(mode="json"))
        return {"saved": True, **scored}

    @app.get("/api/checks/result/{case_id}/{frame_index}")
    def get_check_result(case_id: str, frame_index: int):
        with lock:
            annotation = next(
                (
                    item
                    for item in checks().annotations
                    if item.case_id == case_id and item.frame_index == frame_index
                ),
                None,
            )
        if annotation is None:
            raise HTTPException(403, "save an independent judgment before revealing the prediction")
        return result(annotation)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    import uvicorn

    cv2.setNumThreads(1)
    uvicorn.run(
        create_crown_annotation_app(args.root), host="127.0.0.1", port=args.port, access_log=False
    )


if __name__ == "__main__":
    main()
