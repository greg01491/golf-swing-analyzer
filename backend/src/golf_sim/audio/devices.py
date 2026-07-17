"""Lists usable microphone input devices -- added after finding that the
system-default input (device=None/MME) can fail outright even on a machine
with working hardware, while a specific WASAPI device index works fine.
Mirrors golf_sim.capture.enumerate for cameras."""

from __future__ import annotations

import sounddevice as sd
from pydantic import BaseModel


class AudioDeviceInfo(BaseModel):
    index: int
    name: str
    hostapi: str
    default_samplerate: float


def list_input_devices() -> list[AudioDeviceInfo]:
    hostapis = sd.query_hostapis()
    devices = []
    for index, info in enumerate(sd.query_devices()):
        if info["max_input_channels"] > 0:
            devices.append(
                AudioDeviceInfo(
                    index=index,
                    name=info["name"],
                    hostapi=hostapis[info["hostapi"]]["name"],
                    default_samplerate=info["default_samplerate"],
                )
            )
    return devices


if __name__ == "__main__":
    for device in list_input_devices():
        print(device)
