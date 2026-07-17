"""Audio sources: a real microphone (via sounddevice), and a synthetic
generator so the trigger pipeline is testable without hardware."""

from __future__ import annotations

import time
from typing import Protocol

import numpy as np
import sounddevice as sd

from golf_sim.audio.block import AudioBlock


class AudioSource(Protocol):
    def open(self) -> None: ...
    def read(self) -> AudioBlock | None: ...
    def close(self) -> None: ...


class SounddeviceMicSource:
    def __init__(self, device: int | str | None, samplerate: int = 44100, block_size: int = 2048):
        self.device = device
        self.samplerate = samplerate
        self.block_size = block_size
        self._stream: sd.InputStream | None = None

    def open(self) -> None:
        self._stream = sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.samplerate,
            blocksize=self.block_size,
            dtype="float32",
        )
        self._stream.start()

    def read(self) -> AudioBlock | None:
        assert self._stream is not None, "call open() first"
        data, _overflowed = self._stream.read(self.block_size)
        return AudioBlock(timestamp=time.monotonic(), samples=data[:, 0])

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class SyntheticAudioSource:
    """Paced synthetic audio for tests/dev: plays back a fixed sequence of
    amplitudes (e.g. silence then a loud burst) one block per call."""

    def __init__(
        self,
        amplitudes: list[float],
        samplerate: int = 44100,
        block_size: int = 2048,
    ):
        self.amplitudes = amplitudes
        self.samplerate = samplerate
        self.block_size = block_size
        self._frame_period = block_size / samplerate
        self._next_due: float | None = None
        self._index = 0

    def open(self) -> None:
        self._next_due = time.monotonic()
        self._index = 0

    def read(self) -> AudioBlock | None:
        assert self._next_due is not None, "call open() first"
        if self._index >= len(self.amplitudes):
            return None
        now = time.monotonic()
        if now < self._next_due:
            time.sleep(self._next_due - now)
        amplitude = self.amplitudes[self._index]
        samples = np.full(self.block_size, amplitude, dtype=np.float32)
        self._index += 1
        self._next_due += self._frame_period
        return AudioBlock(timestamp=time.monotonic(), samples=samples)

    def close(self) -> None:
        self._next_due = None
