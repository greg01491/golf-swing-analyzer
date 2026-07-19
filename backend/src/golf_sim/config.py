"""Loads config/config.yaml into typed settings. Single source of truth for
every tunable parameter (spec.md NFR4) -- add new fields here, not as bare
constants elsewhere."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"


class AudioTriggerConfig(BaseModel):
    device: int | str | None = None
    threshold_db: float
    pre_capture_delay_s: float
    capture_duration_s: float
    trigger_cooldown_s: float


class CameraDeviceConfig(BaseModel):
    id: int
    role: str
    width: int
    height: int
    fps: int
    # DirectShow device name; when set, takes precedence over id because
    # Windows camera indices are not stable across processes.
    name: str | None = None
    # Corrects a physically sideways/upside-down mounted camera. Applied to
    # every frame at capture time (not just the live preview) since a
    # rotated person confuses the pose model, which is trained on upright
    # people -- this is an accuracy fix, not a cosmetic one.
    rotation_deg: Literal[0, 90, 180, 270] = 0


class CamerasConfig(BaseModel):
    buffer_margin_s: float
    devices: list[CameraDeviceConfig]


class PoseConfig(BaseModel):
    pose_model: str
    mode: str
    save_debug_video: bool


class CalibrationConfig(BaseModel):
    dir: str
    max_age_days: int
    checkerboard_corners: list[int]
    checkerboard_square_size_mm: float


class ReferenceRange(BaseModel):
    min: float
    max: float


class MetricsConfig(BaseModel):
    reference_ranges: dict[str, ReferenceRange]


class AnalysisConfig(BaseModel):
    # Which arm is "lead" (closer to the target) -- needed to interpret P-system
    # checkpoints (P3/P5/P9 etc. are defined relative to the lead arm) since
    # body-pose tracking alone can't infer this from the footage.
    golfer_handedness: Literal["right", "left"] = "right"


class ProcessingConfig(BaseModel):
    auto_process: bool


class StorageConfig(BaseModel):
    data_dir: str
    db_file: str


class ApiConfig(BaseModel):
    host: str
    port: int


class Config(BaseModel):
    audio_trigger: AudioTriggerConfig
    cameras: CamerasConfig
    pose: PoseConfig
    calibration: CalibrationConfig
    metrics: MetricsConfig
    analysis: AnalysisConfig
    processing: ProcessingConfig
    storage: StorageConfig
    api: ApiConfig


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config.model_validate(raw)
