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


def resolve_input_device(device: int | str | None) -> int | None:
    """Resolve a configured input, recovering when Windows renumbers devices."""
    hostapis = sd.query_hostapis()
    devices = sd.query_devices()

    if device is not None:
        try:
            if isinstance(device, str):
                hostapi_name, separator, device_name = device.partition(":")
                for index, info in enumerate(devices):
                    if (
                        info["max_input_channels"] > 0
                        and info["name"] == (device_name if separator else hostapi_name)
                        and (not separator or hostapis[info["hostapi"]]["name"] == hostapi_name)
                    ):
                        return index
                raise ValueError(f"configured input device is unavailable: {device}")
            info = sd.query_devices(device)
            if info["max_input_channels"] > 0:
                return device
        except (ValueError, sd.PortAudioError):
            pass

    candidates = [
        (index, info) for index, info in enumerate(devices) if info["max_input_channels"] > 0
    ]
    if not candidates:
        raise RuntimeError("no microphone input devices are available")
    wasapi = [index for index, info in candidates if "WASAPI" in hostapis[info["hostapi"]]["name"]]
    return wasapi[0] if wasapi else candidates[0][0]


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
