from golf_sim.config import DEFAULT_CONFIG_PATH, load_config

METRIC_NAMES = {
    "shoulder_turn_deg",
    "hip_turn_deg",
    "x_factor_deg",
    "spine_tilt_deg",
    "tempo_ratio",
    "hip_sway_top_pct",
    "hip_sway_impact_pct",
    "hip_rotation_impact_deg",
    "backswing_time_s",
    "downswing_time_s",
    "shoulder_tilt_impact_deg",
    "spine_angle_change_deg",
    "head_movement_cm",
    "early_extension_cm",
    "reverse_spine_deg",
    "knee_flex_deg",
    "lead_arm_deg",
    "hand_speed_impact_ms",
    "swing_plane_deg",
}


def test_load_config_default_path():
    cfg = load_config()
    assert len(cfg.cameras.devices) == 2
    assert cfg.audio_trigger.pre_capture_delay_s == 1.5
    assert cfg.ball.hue_min == 15
    assert cfg.ball.roi.x_min_offset == -140


def test_default_config_path_exists():
    assert DEFAULT_CONFIG_PATH.exists()


def test_all_clubs_resolve_ranges_for_every_metric():
    config = load_config()

    assert METRIC_NAMES <= config.metrics.reference_ranges.keys()
    for club in config.metrics.club_profile_mapping:
        assert METRIC_NAMES <= config.metrics.ranges_for_club(club).keys()
