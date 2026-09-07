"""Camera hardware capability check -- opens each configured camera briefly,
measures what it actually delivers (resolution + a real measured frame rate,
not just what the driver claims to support), and compares against
config.yaml's system_requirements. Surfaced in the UI so a camera that can't
really sustain 720p/30fps+ is flagged before someone captures a fast swing on
hardware that will blur or drop the critical impact frame, rather than
discovering it after a failed calibration.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

from golf_sim.capture.source import apply_camera_controls, resolve_camera_index
from golf_sim.config import CameraDeviceConfig, SystemRequirementsConfig

_SAMPLE_FRAMES = 15
# Auto-exposure/white-balance settling on first open can otherwise masquerade
# as a slow camera -- found live: the same hardware measured 60fps moments
# after backend startup, then ~1fps on a later check, purely from warm-up
# timing. Frames are discarded (not measured) for this long before timing.
_WARMUP_S = 1.5
# Hard ceiling on the whole probe (index resolution + open + warm-up +
# sampling). A stalled driver's read() call has no built-in timeout and can
# block forever -- this must never hang the request indefinitely just
# because one camera's USB connection is flaky.
_PROBE_TIMEOUT_S = 8.0


class _Capture(Protocol):
    def isOpened(self) -> bool: ...
    def set(self, prop_id: int, value: float) -> bool: ...
    def get(self, prop_id: int) -> float: ...
    def read(self) -> tuple[bool, object]: ...
    def release(self) -> None: ...


def _default_open(index: int, width: int, height: int, fps: float) -> _Capture:
    import cv2

    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)
    return cap


@dataclass
class CameraCheckResult:
    role: str
    name: str | None
    opened: bool
    requested_width: int
    requested_height: int
    requested_fps: float
    actual_width: int | None = None
    actual_height: int | None = None
    measured_fps: float | None = None
    controls: dict[str, dict[str, float | bool | None]] = field(default_factory=dict)
    sharpness: float | None = None
    brightness: float | None = None
    meets_minimum: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def _probe(
    dev: CameraDeviceConfig, open_capture, warmup_s: float
) -> tuple[int, int, float | None, dict, float | None, float | None]:
    """Runs on a worker thread (see check_camera) -- may block indefinitely
    on a stalled camera, so nothing here must be relied on to return
    promptly."""
    import cv2

    index = dev.id if dev.name is None else resolve_camera_index(dev.name)
    cap = open_capture(index, dev.width, dev.height, dev.fps)
    try:
        if not cap.isOpened():
            raise RuntimeError(f"could not open camera {dev.name or index!r}")
        controls = apply_camera_controls(cap, dev)
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        warmup_deadline = time.monotonic() + warmup_s
        while time.monotonic() < warmup_deadline:
            cap.read()

        start = time.monotonic()
        grabbed = 0
        sample_frame = None
        for _ in range(_SAMPLE_FRAMES):
            ok, frame = cap.read()
            if ok:
                grabbed += 1
                if sample_frame is None:
                    sample_frame = frame
        elapsed = time.monotonic() - start
        measured_fps = round(grabbed / elapsed, 1) if elapsed > 0 else None
        sharpness = None
        brightness = None
        if sample_frame is not None:
            import numpy as np

            if isinstance(sample_frame, np.ndarray) and sample_frame.size:
                gray = cv2.cvtColor(sample_frame, cv2.COLOR_BGR2GRAY)
                sharpness = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 2)
                brightness = round(float(gray.mean()), 2)
        return actual_width, actual_height, measured_fps, controls, sharpness, brightness
    finally:
        cap.release()


def check_camera(
    dev: CameraDeviceConfig,
    requirements: SystemRequirementsConfig,
    open_capture=_default_open,
    probe_timeout_s: float = _PROBE_TIMEOUT_S,
    warmup_s: float = _WARMUP_S,
) -> CameraCheckResult:
    result = CameraCheckResult(
        role=dev.role,
        name=dev.name,
        opened=False,
        requested_width=dev.width,
        requested_height=dev.height,
        requested_fps=dev.fps,
    )

    outcome: dict = {}

    def worker() -> None:
        try:
            outcome["value"] = _probe(dev, open_capture, warmup_s)
        except Exception as exc:  # noqa: BLE001 -- surfaced as a diagnostic message, not raised
            outcome["error"] = str(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(probe_timeout_s)
    if thread.is_alive():
        result.error = (
            f"camera {dev.name or dev.id!r} did not respond within "
            f"{probe_timeout_s:.0f}s -- it may be stalled; try reconnecting it"
        )
        return result
    if "error" in outcome:
        result.error = outcome["error"]
        return result

    result.opened = True
    (
        result.actual_width,
        result.actual_height,
        result.measured_fps,
        result.controls,
        result.sharpness,
        result.brightness,
    ) = outcome["value"]

    warnings: list[str] = []
    minimum_failed = False
    if (
        result.actual_width < requirements.min_camera_width
        or result.actual_height < requirements.min_camera_height
    ):
        minimum_failed = True
        warnings.append(
            f"camera only delivers {result.actual_width}x{result.actual_height} "
            f"(minimum {requirements.min_camera_width}x{requirements.min_camera_height})"
        )
    if result.measured_fps is not None and result.measured_fps < requirements.min_camera_fps:
        minimum_failed = True
        warnings.append(
            f"camera only sustains ~{result.measured_fps} fps "
            f"(minimum {requirements.min_camera_fps}) -- fast swing motion may blur or drop frames"
        )
    if (
        result.brightness is not None
        and result.brightness < requirements.min_camera_brightness
    ):
        warnings.append(
            f"camera sample is dark ({result.brightness:.1f} brightness; "
            f"recommended minimum {requirements.min_camera_brightness:.1f}) -- "
            "motion blur may increase"
        )
    if (
        result.sharpness is not None
        and result.sharpness < requirements.min_camera_sharpness
    ):
        warnings.append(
            f"camera sample is soft ({result.sharpness:.1f} sharpness; "
            f"recommended minimum {requirements.min_camera_sharpness:.1f}) -- "
            "check focus or lighting"
        )
    result.warnings = warnings
    result.meets_minimum = not minimum_failed
    return result
