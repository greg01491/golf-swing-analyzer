"""Threshold + cooldown logic (FR2/FR3/FR7), decoupled from any I/O so it's
trivially unit-testable."""

from __future__ import annotations


class TriggerDetector:
    def __init__(self, threshold_db: float, cooldown_s: float):
        self.threshold_db = threshold_db
        self.cooldown_s = cooldown_s
        self._last_trigger_time: float | None = None

    def check(self, level_db: float, now: float) -> bool:
        if level_db < self.threshold_db:
            return False
        if (
            self._last_trigger_time is not None
            and (now - self._last_trigger_time) < self.cooldown_s
        ):
            return False
        self._last_trigger_time = now
        return True

    def reset_cooldown(self, now: float) -> None:
        """Used by a manual trigger (FR8) so it still starts a cooldown
        window, even though it bypasses the threshold/cooldown check itself."""
        self._last_trigger_time = now
