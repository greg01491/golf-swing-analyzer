from unittest.mock import patch

import sounddevice as sd

from golf_sim.audio.devices import list_input_devices, resolve_input_device


def test_list_input_devices_returns_input_capable_devices():
    devices = list_input_devices()
    assert isinstance(devices, list)
    for device in devices:
        assert device.index >= 0
        assert device.name
        assert device.default_samplerate > 0


def test_invalid_device_falls_back_to_first_wasapi_input():
    devices = [
        {"name": "speaker", "max_input_channels": 0, "hostapi": 0},
        {"name": "webcam mic", "max_input_channels": 1, "hostapi": 0},
        {"name": "array mic", "max_input_channels": 2, "hostapi": 1},
    ]
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    with (
        patch.object(
            sd,
            "query_devices",
            side_effect=lambda device=None: (
                devices if device is None else (_ for _ in ()).throw(ValueError())
            ),
        ),
        patch.object(sd, "query_hostapis", return_value=hostapis),
    ):
        assert resolve_input_device(99) == 2


def test_named_wasapi_device_survives_index_changes():
    devices = [
        {"name": "array mic", "max_input_channels": 2, "hostapi": 0},
        {"name": "array mic", "max_input_channels": 2, "hostapi": 1},
    ]
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    with (
        patch.object(sd, "query_devices", return_value=devices),
        patch.object(sd, "query_hostapis", return_value=hostapis),
    ):
        assert resolve_input_device("Windows WASAPI:array mic") == 1
