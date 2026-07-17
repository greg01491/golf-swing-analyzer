from golf_sim.audio.trigger import TriggerDetector


def test_below_threshold_does_not_trigger():
    detector = TriggerDetector(threshold_db=-20.0, cooldown_s=1.0)
    assert detector.check(level_db=-30.0, now=0.0) is False


def test_above_threshold_triggers():
    detector = TriggerDetector(threshold_db=-20.0, cooldown_s=1.0)
    assert detector.check(level_db=-10.0, now=0.0) is True


def test_cooldown_suppresses_retrigger():
    detector = TriggerDetector(threshold_db=-20.0, cooldown_s=1.0)
    assert detector.check(level_db=-10.0, now=0.0) is True
    assert detector.check(level_db=-10.0, now=0.5) is False  # within cooldown
    assert detector.check(level_db=-10.0, now=1.5) is True  # cooldown elapsed


def test_reset_cooldown_blocks_immediate_retrigger():
    detector = TriggerDetector(threshold_db=-20.0, cooldown_s=1.0)
    detector.reset_cooldown(now=0.0)
    assert detector.check(level_db=-10.0, now=0.2) is False
