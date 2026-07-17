"""Dev/test entrypoint for the audio trigger service.

    python -m golf_sim.audio.cli listen [--synthetic]
    python -m golf_sim.audio.cli calibrate [--synthetic]

"listen" arms the mic and wires trigger events into the capture pipeline
(FR8's manual arm/disarm + manual re-trigger fallback live here as CLI
commands: type "t" to trigger manually, "a"/"d" to arm/disarm, "q" to quit).
"""

from __future__ import annotations

import argparse

from golf_sim.audio.calibration import run_calibration
from golf_sim.audio.devices import list_input_devices
from golf_sim.audio.service import AudioTriggerService
from golf_sim.audio.source import AudioSource, SounddeviceMicSource, SyntheticAudioSource
from golf_sim.audio.trigger import TriggerDetector
from golf_sim.capture.service import CaptureService
from golf_sim.capture.source import SyntheticCameraSource
from golf_sim.config import Config, load_config


def _build_audio_source(config: Config, synthetic: bool) -> AudioSource:
    if synthetic:
        # quiet / loud "impact" burst / quiet again, so a demo run without
        # hardware still exercises an automatic trigger.
        amplitudes = [0.001] * 30 + [0.5] * 3 + [0.001] * 60
        return SyntheticAudioSource(amplitudes=amplitudes)
    return SounddeviceMicSource(device=config.audio_trigger.device)


def _run_listen(config: Config, synthetic: bool) -> None:
    camera_sources = None
    if synthetic:
        camera_sources = {
            dev.role: SyntheticCameraSource(fps=dev.fps, width=dev.width, height=dev.height)
            for dev in config.cameras.devices
        }
    capture_service = CaptureService(config, sources=camera_sources)
    capture_service.start()

    def on_trigger(trigger_time: float) -> None:
        print(f"\n[trigger] at {trigger_time:.3f} -- saving session...")
        session_dir = capture_service.capture_now(trigger_time)
        print(f"[trigger] session saved to {session_dir}")

    audio_source = _build_audio_source(config, synthetic)
    detector = TriggerDetector(
        threshold_db=config.audio_trigger.threshold_db,
        cooldown_s=config.audio_trigger.trigger_cooldown_s,
    )
    audio_service = AudioTriggerService(audio_source, detector, on_trigger)
    audio_service.start()
    audio_service.arm()

    print("Armed and listening. Commands: t=manual trigger, a=arm, d=disarm, q=quit")
    try:
        while True:
            level = audio_service.last_level_db
            level_str = f"{level:.1f} dB" if level is not None else "..."
            cmd = input(f"[level {level_str}] > ").strip().lower()
            if cmd == "t":
                audio_service.manual_trigger()
            elif cmd == "a":
                audio_service.arm()
                print("armed")
            elif cmd == "d":
                audio_service.disarm()
                print("disarmed")
            elif cmd == "q":
                break
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        audio_service.stop()
        capture_service.stop()
        print("stopped")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    listen_parser = subparsers.add_parser("listen", help="arm and listen for triggers")
    listen_parser.add_argument("--synthetic", action="store_true")

    calibrate_parser = subparsers.add_parser("calibrate", help="suggest a trigger threshold")
    calibrate_parser.add_argument("--synthetic", action="store_true")

    subparsers.add_parser("devices", help="list usable microphone input devices")

    args = parser.parse_args()

    if args.command == "devices":
        print("Listed devices aren't guaranteed to open -- not all backends support the")
        print("blocking read this app uses. WASAPI entries are the most reliable bet;")
        print("try one with `listen --synthetic`-style testing before committing to it")
        print("in config.yaml's audio_trigger.device.\n")
        for device in list_input_devices():
            print(device)
        return

    config = load_config()
    if args.command == "listen":
        _run_listen(config, synthetic=args.synthetic)
    elif args.command == "calibrate":
        source = _build_audio_source(config, synthetic=args.synthetic)
        run_calibration(source)


if __name__ == "__main__":
    main()
