from golf_sim.config import SystemRequirementsConfig
from golf_sim.diagnostics.system_check import check_system


def _requirements(**overrides) -> SystemRequirementsConfig:
    base = dict(
        min_cpu_cores=1,
        recommended_cpu_cores=1,
        min_ram_gb=0.001,
        recommended_ram_gb=0.001,
        min_free_disk_gb=0.001,
        high_cpu_load_pct=101,  # effectively unreachable, unless overridden
        high_ram_used_pct=101,
    )
    base.update(overrides)
    return SystemRequirementsConfig(**base)


def test_passes_when_requirements_are_trivially_met(tmp_path):
    result = check_system(tmp_path, _requirements())
    assert result.meets_minimum is True
    assert result.meets_recommended is True
    assert result.warnings == []


def test_handles_data_dir_that_does_not_exist_yet(tmp_path):
    # data_dir is created lazily on the first capture -- a fresh install
    # must not crash trying to check disk space before that happens
    missing = tmp_path / "not-created-yet" / "nested"
    result = check_system(missing, _requirements())
    assert result.free_disk_gb > 0


def test_flags_insufficient_cpu_cores(tmp_path):
    result = check_system(tmp_path, _requirements(min_cpu_cores=10_000))
    assert result.meets_minimum is False
    assert any("CPU cores" in w for w in result.warnings)


def test_flags_insufficient_ram(tmp_path):
    result = check_system(tmp_path, _requirements(min_ram_gb=10_000))
    assert result.meets_minimum is False
    assert any("RAM" in w for w in result.warnings)


def test_flags_insufficient_disk_space(tmp_path):
    result = check_system(tmp_path, _requirements(min_free_disk_gb=10_000_000))
    assert result.meets_minimum is False
    assert any("disk space" in w for w in result.warnings)


def test_flags_high_current_load(tmp_path):
    result = check_system(tmp_path, _requirements(high_cpu_load_pct=-1, high_ram_used_pct=-1))
    assert any("close other applications" in w for w in result.warnings)
    # minimum hardware specs are still fine even though current load is flagged
    assert result.meets_minimum is True
