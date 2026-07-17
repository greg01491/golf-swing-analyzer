"""Given a trigger time, pull the correctly-windowed clip out of a rolling
buffer: [trigger_time - pre_capture_delay_s, + capture_duration_s] (FR4/FR5)."""

from __future__ import annotations

import time

from golf_sim.capture.buffer import RollingBuffer
from golf_sim.capture.frame import Frame


class ExtractTimeoutError(RuntimeError):
    pass


def extract_window(
    buffer: RollingBuffer,
    trigger_time: float,
    pre_capture_delay_s: float,
    capture_duration_s: float,
    poll_interval_s: float = 0.02,
    timeout_s: float = 10.0,
) -> list[Frame]:
    start_time = trigger_time - pre_capture_delay_s
    end_time = start_time + capture_duration_s

    deadline = time.monotonic() + timeout_s
    while True:
        latest = buffer.latest_timestamp()
        if latest is not None and latest >= end_time:
            break
        if time.monotonic() > deadline:
            raise ExtractTimeoutError(f"buffer never reached end_time={end_time}; latest={latest}")
        time.sleep(poll_interval_s)

    return [f for f in buffer.snapshot() if start_time <= f.timestamp <= end_time]
