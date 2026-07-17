from golf_sim.config import DEFAULT_CONFIG_PATH, load_config


def test_load_config_default_path():
    cfg = load_config()
    assert len(cfg.cameras.devices) == 2
    assert cfg.audio_trigger.pre_capture_delay_s == 1.0


def test_default_config_path_exists():
    assert DEFAULT_CONFIG_PATH.exists()
