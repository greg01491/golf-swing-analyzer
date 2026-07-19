"""PC hardware spec check (CPU/RAM/disk) against config.yaml's
system_requirements -- surfaced in the UI so an under-specced machine is
flagged before someone spends a session capturing on hardware that can't
keep up, rather than discovering it via dropped frames or slow processing.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import psutil

from golf_sim.config import SystemRequirementsConfig


@dataclass
class SystemCheckResult:
    cpu_cores: int
    ram_gb: float
    free_disk_gb: float
    cpu_load_pct: float
    ram_used_pct: float
    meets_minimum: bool
    meets_recommended: bool
    warnings: list[str] = field(default_factory=list)


def _existing_ancestor(path: Path) -> Path:
    """data_dir may not exist yet on a fresh install (created lazily on the
    first capture) -- shutil.disk_usage requires a real path, so walk up
    until one is found. Any ancestor is on the same volume/drive."""
    path = Path(path).resolve()
    while not path.exists():
        parent = path.parent
        if parent == path:
            break
        path = parent
    return path


def check_system(data_dir: Path, requirements: SystemRequirementsConfig) -> SystemCheckResult:
    cpu_cores = os.cpu_count() or 1
    vm = psutil.virtual_memory()
    ram_gb = vm.total / (1024**3)
    free_disk_gb = shutil.disk_usage(_existing_ancestor(data_dir)).free / (1024**3)
    # a brief sample so this isn't just one noisy instantaneous reading
    cpu_load_pct = psutil.cpu_percent(interval=0.3)
    ram_used_pct = vm.percent

    warnings: list[str] = []
    meets_minimum = True
    if cpu_cores < requirements.min_cpu_cores:
        meets_minimum = False
        warnings.append(
            f"only {cpu_cores} CPU cores detected (minimum {requirements.min_cpu_cores}) "
            "-- pose processing will be slow"
        )
    if ram_gb < requirements.min_ram_gb:
        meets_minimum = False
        warnings.append(f"only {ram_gb:.1f} GB RAM detected (minimum {requirements.min_ram_gb} GB)")
    if free_disk_gb < requirements.min_free_disk_gb:
        meets_minimum = False
        warnings.append(
            f"only {free_disk_gb:.1f} GB free disk space "
            f"(minimum {requirements.min_free_disk_gb} GB) -- sessions may fail to save"
        )

    meets_recommended = (
        cpu_cores >= requirements.recommended_cpu_cores
        and ram_gb >= requirements.recommended_ram_gb
        and meets_minimum
    )

    if cpu_load_pct > requirements.high_cpu_load_pct:
        warnings.append(
            f"CPU is already at {cpu_load_pct:.0f}% usage -- "
            "close other applications before capturing"
        )
    if ram_used_pct > requirements.high_ram_used_pct:
        warnings.append(
            f"RAM is already {ram_used_pct:.0f}% used -- close other applications before capturing"
        )

    return SystemCheckResult(
        cpu_cores=cpu_cores,
        ram_gb=round(ram_gb, 1),
        free_disk_gb=round(free_disk_gb, 1),
        cpu_load_pct=cpu_load_pct,
        ram_used_pct=ram_used_pct,
        meets_minimum=meets_minimum,
        meets_recommended=meets_recommended,
        warnings=warnings,
    )
