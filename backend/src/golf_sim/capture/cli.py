"""Manual "capture now" dev/test entrypoint (FR8 fallback + Phase 1 exit
criteria). Usage:

    python -m golf_sim.capture.cli            # real USB cameras from config.yaml
    python -m golf_sim.capture.cli --synthetic # no hardware required
"""

from __future__ import annotations

import argparse
import time

from golf_sim.capture.service import CaptureService
from golf_sim.capture.source import SyntheticCameraSource
from golf_sim.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="use synthetic camera sources instead of real USB cameras",
    )
    args = parser.parse_args()

    config = load_config()

    sources = None
    if args.synthetic:
        sources = {
            dev.role: SyntheticCameraSource(fps=dev.fps, width=dev.width, height=dev.height)
            for dev in config.cameras.devices
        }

    service = CaptureService(config, sources=sources)
    service.start()

    warmup_s = config.audio_trigger.pre_capture_delay_s + config.cameras.buffer_margin_s
    print(f"warming up buffers for {warmup_s:.1f}s...")
    time.sleep(warmup_s)

    print("capturing now...")
    session_dir = service.capture_now()

    service.stop()
    print(f"session saved to {session_dir}")


if __name__ == "__main__":
    main()
