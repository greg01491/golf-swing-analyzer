"""Loads config/config.yaml into typed settings. Single source of truth for
every tunable parameter (spec.md NFR4) -- add new fields here, not as bare
constants elsewhere."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"
CURRENT_METRIC_RANGE_DEFINITION_VERSION = 2


def user_state_root() -> Path:
    """Writable per-user directory for captures, calibration and the database."""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "golf-swing-analyzer"
    return Path.home() / ".local" / "share" / "golf-swing-analyzer"


def shipped_config_path() -> Path:
    """Locate bundled defaults in frozen builds, with the source file as fallback."""
    if getattr(sys, "frozen", False):
        packaged_default = Path(sys.executable).resolve().parent.parent / "defaults" / "config.yaml"
        if packaged_default.is_file():
            return packaged_default
    return DEFAULT_CONFIG_PATH


def resolve_state_path(value: str | Path) -> Path:
    """Resolve a configured storage path to an absolute, writable location.

    config.yaml ships relative defaults ("data") that are fine from a source
    checkout but disastrous in the packaged app: REPO_ROOT then points inside
    the install directory (Program Files for an all-users install), so every
    write dies with PermissionError. In a frozen build relative paths are
    therefore resolved against the per-user state directory instead.
    """
    path = Path(value)
    if path.is_absolute():
        return path
    if getattr(sys, "frozen", False):
        return user_state_root() / path
    return REPO_ROOT / path


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
    # Optional DirectShow image controls. null preserves the camera driver's
    # current behavior for rigs that do not expose a given control.
    auto_exposure: bool | None = None
    exposure: float | None = None
    gain: float | None = None
    autofocus: bool | None = None
    focus: float | None = None
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


class CrownTrackingDiagnosticConfig(BaseModel):
    min_confidence: float = Field(default=0.3, ge=0, le=1)
    feature_radius_px: int = Field(default=24, ge=1)
    max_features: int = Field(default=60, ge=6)
    feature_quality: float = Field(default=0.01, gt=0, lt=1)
    min_feature_distance_px: float = Field(default=3.0, gt=0)
    min_features: int = Field(default=6, ge=3)
    lk_window_px: int = Field(default=21, ge=3)
    lk_max_level: int = Field(default=3, ge=0)
    max_forward_backward_error_px: float = Field(default=1.0, gt=0)
    ransac_reprojection_px: float = Field(default=1.5, gt=0)
    min_inlier_fraction: float = Field(default=0.6, gt=0, le=1)
    max_detector_disagreement_px: float = Field(default=12.0, gt=0)


class PoseConfig(BaseModel):
    pose_model: str
    mode: str
    save_debug_video: bool
    crown_tracking_diagnostic: CrownTrackingDiagnosticConfig = Field(
        default_factory=CrownTrackingDiagnosticConfig
    )
    parallel_workers_pose: Literal[1, 2] = 1
    parallel_workers_pose: Literal[1, 2] = 1


class CalibrationValidationConfig(BaseModel):
    max_lens_rms_px: float = Field(default=5.0, gt=0)
    max_median_error_px: float = Field(default=5.0, gt=0)
    max_tail_error_px: float = Field(default=15.0, gt=0)
    min_coverage: float = Field(default=0.8, gt=0, le=1)
    min_positive_depth: float = Field(default=0.95, gt=0, le=1)
    min_fit_correspondences: int = Field(default=100, ge=8)
    min_heldout_correspondences: int = Field(default=100, ge=8)
    min_heldout_frames: int = Field(default=20, ge=2)
    heldout_fraction: float = Field(default=0.25, gt=0, lt=0.5)
    partition_gap_s: float = Field(default=0.25, ge=0)
    max_reference_error_px: float = Field(default=2.0, gt=0)
    max_normal_difference_deg: float = Field(default=3.0, gt=0, lt=90)
    max_length_relative_error: float = Field(default=0.05, gt=0, lt=1)
    min_board_span_px: float = Field(default=80.0, gt=0)


class CalibrationConfig(BaseModel):
    dir: str
    max_age_days: int
    checkerboard_corners: list[int]
    checkerboard_square_size_mm: float
    camera_distance_m: float = 3.115
    validation: CalibrationValidationConfig = Field(default_factory=CalibrationValidationConfig)


class ReferenceRange(BaseModel):
    min: float
    max: float


Club = Literal[
    "driver",
    "3_wood",
    "5_wood",
    "3_iron",
    "4_iron",
    "5_iron",
    "6_iron",
    "7_iron",
    "8_iron",
    "9_iron",
    "pitching_wedge",
    "gap_wedge",
    "sand_wedge",
    "lob_wedge",
]

CLUB_LABELS: dict[Club, str] = {
    "driver": "Driver",
    "3_wood": "3 wood",
    "5_wood": "5 wood",
    "3_iron": "3 iron",
    "4_iron": "4 iron",
    "5_iron": "5 iron",
    "6_iron": "6 iron",
    "7_iron": "7 iron",
    "8_iron": "8 iron",
    "9_iron": "9 iron",
    "pitching_wedge": "Pitching wedge",
    "gap_wedge": "Gap wedge",
    "sand_wedge": "Sand wedge",
    "lob_wedge": "Lob wedge",
}


class MetricsConfig(BaseModel):
    reference_ranges: dict[str, ReferenceRange]
    range_definition_version: int | None = Field(default=None, ge=1)
    club_profiles: dict[str, dict[str, ReferenceRange]] = Field(default_factory=dict)
    club_profile_mapping: dict[Club, str] = Field(default_factory=dict)
    turn_filter_window_s: float = Field(default=0.05, gt=0)
    address_window_s: float = Field(default=0.1, gt=0)
    turn_outlier_deg: float = Field(default=20.0, gt=0, lt=180)
    min_projected_width_m: float = Field(default=0.02, gt=0)
    min_supported_fraction: float = Field(default=0.8, gt=0, le=1)
    frozen_tolerance_m: float = Field(default=0.0001, gt=0)
    hand_speed_window_s: float = Field(default=0.1, gt=0)
    max_marker_speed_ms: float = Field(default=20.0, gt=0)
    max_limb_length_ratio: float = Field(default=1.5, gt=1)
    min_pelvis_height_m: float = Field(default=0.3, gt=0)
    max_pelvis_height_m: float = Field(default=1.5, gt=0)
    held_observation_motion_px: float = Field(default=2.0, gt=0)
    marker_outlier_distance_m: float = Field(default=0.05, gt=0)

    @model_validator(mode="after")
    def validate_height_bounds(self) -> MetricsConfig:
        if self.max_pelvis_height_m <= self.min_pelvis_height_m:
            raise ValueError("max_pelvis_height_m must exceed min_pelvis_height_m")
        return self

    def ranges_for_club(self, club: Club | None) -> dict[str, ReferenceRange]:
        ranges = dict(self.reference_ranges)
        if club is not None:
            profile = self.club_profile_mapping.get(club)
            if profile is not None:
                ranges.update(self.club_profiles.get(profile, {}))
        return ranges


class AnalysisConfig(BaseModel):
    # Which arm is "lead" (closer to the target) -- needed to interpret P-system
    # checkpoints (P3/P5/P9 etc. are defined relative to the lead arm) since
    # body-pose tracking alone can't infer this from the footage.
    golfer_handedness: Literal["right", "left"] = "right"


class BallROICoords(BaseModel):
    # ROI offsets relative to the chosen anchor point (wrists or feet).
    x_min_offset: int = -140
    x_max_offset: int = 140
    y_min_offset: int = 100
    y_max_offset: int = 320


class BallConfig(BaseModel):
    # OpenCV hue range (0-179) for the coloured ball. The ball is yellow
    # (measured hue ~22-30); this range excludes skin/orange below and the
    # green mat above.
    hue_min: int = 15
    hue_max: int = 42
    # Use the face-on camera for ball/club contact: the ball is clearer there.
    detection_camera_role: str = "camera_2"
    # In the face-on view the ball sits below the golfer's feet, so anchor the
    # search on the feet rather than the wrists.
    detection_anchor: Literal["wrists", "feet", "legs"] = "legs"
    min_saturation: int = 50
    min_value: int = 50
    min_circularity: float = 0.4
    min_area_px: float = 20.0
    present_min_fraction: float = 0.1
    disappearance_confirm_frames: int = 2
    roi: BallROICoords = Field(default_factory=BallROICoords)


class ProcessingConfig(BaseModel):
    auto_process: bool


class StorageConfig(BaseModel):
    data_dir: str
    db_file: str


class ApiConfig(BaseModel):
    host: str
    port: int


class SystemRequirementsConfig(BaseModel):
    # Below "minimum" is flagged as likely too slow/unreliable for capture +
    # pose processing; below "recommended" still works but may be sluggish.
    min_cpu_cores: int = 4
    recommended_cpu_cores: int = 8
    min_ram_gb: float = 8.0
    recommended_ram_gb: float = 16.0
    min_free_disk_gb: float = 5.0
    # Golf swings are fast -- a camera that can't sustain these gets motion
    # blur or drops the critical impact frame entirely.
    min_camera_width: int = 1280
    min_camera_height: int = 720
    min_camera_fps: float = 30.0
    min_camera_brightness: float = 20.0
    min_camera_sharpness: float = 5.0
    # "close other applications" warning thresholds for current system load.
    high_cpu_load_pct: float = 70.0
    high_ram_used_pct: float = 80.0


class Config(BaseModel):
    audio_trigger: AudioTriggerConfig
    cameras: CamerasConfig
    pose: PoseConfig
    calibration: CalibrationConfig
    metrics: MetricsConfig
    analysis: AnalysisConfig
    ball: BallConfig = Field(default_factory=BallConfig)
    processing: ProcessingConfig
    storage: StorageConfig
    api: ApiConfig
    system_requirements: SystemRequirementsConfig = Field(default_factory=SystemRequirementsConfig)


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)
    return Config.model_validate(raw)
