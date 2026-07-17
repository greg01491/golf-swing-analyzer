import time

from golf_sim.audio.service import AudioTriggerService
from golf_sim.audio.source import SyntheticAudioSource
from golf_sim.audio.trigger import TriggerDetector

_BLOCK_SIZE = 256
_SAMPLERATE = 44100
_BLOCK_PERIOD_S = _BLOCK_SIZE / _SAMPLERATE


def _run_service(amplitudes, threshold_db=-20.0, cooldown_s=0.03, armed=True):
    source = SyntheticAudioSource(
        amplitudes=amplitudes, samplerate=_SAMPLERATE, block_size=_BLOCK_SIZE
    )
    detector = TriggerDetector(threshold_db=threshold_db, cooldown_s=cooldown_s)
    triggers: list[float] = []
    service = AudioTriggerService(source, detector, on_trigger=triggers.append)

    service.start()
    if armed:
        service.arm()
    time.sleep(len(amplitudes) * _BLOCK_PERIOD_S + 0.15)
    service.stop()
    return triggers


def test_loud_burst_triggers_once_per_cooldown_window():
    # two loud bursts separated by a quiet gap comfortably longer than cooldown
    amplitudes = [0.001] * 5 + [0.5] * 3 + [0.001] * 10 + [0.5] * 3 + [0.001] * 10
    triggers = _run_service(amplitudes, cooldown_s=0.03)
    assert len(triggers) == 2


def test_quiet_audio_never_triggers():
    triggers = _run_service([0.001] * 30)
    assert triggers == []


def test_disarmed_service_does_not_trigger():
    amplitudes = [0.5] * 20
    triggers = _run_service(amplitudes, armed=False)
    assert triggers == []


def test_manual_trigger_fires_even_when_disarmed():
    source = SyntheticAudioSource(amplitudes=[0.001] * 20, block_size=_BLOCK_SIZE)
    detector = TriggerDetector(threshold_db=-20.0, cooldown_s=1.0)
    triggers: list[float] = []
    service = AudioTriggerService(source, detector, on_trigger=triggers.append)

    service.start()  # not armed
    service.manual_trigger()
    time.sleep(0.05)
    service.stop()

    assert len(triggers) == 1
