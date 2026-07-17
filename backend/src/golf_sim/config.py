"""Loads config/config.yaml into typed settings. Single source of truth for
every tunable parameter (spec.md NFR4) -- add new fields here, not as bare
constants elsewhere."""

from __future__ import annotations

from pathlib import Path

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


class CamerasConfig(BaseModel):
    buffer_margin_s: float
    devices: list[CameraDeviceConfig]


class PoseConfig(BaseModel):
    model: str


class CalibrationConfig(BaseModel):
    file: str


class ReferenceRange(BaseModel):
    min: float
    max: float


class MetricsConfig(BaseModel):
    reference_ranges: dict[str, ReferenceRange]


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
    storage: StorageConfig
    api: ApiConfig


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config.model_validate(raw)
