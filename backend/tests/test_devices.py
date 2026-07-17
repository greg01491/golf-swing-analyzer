from golf_sim.audio.devices import list_input_devices


def test_list_input_devices_returns_input_capable_devices():
    devices = list_input_devices()
    assert isinstance(devices, list)
    for device in devices:
        assert device.index >= 0
        assert device.name
        assert device.default_samplerate > 0
