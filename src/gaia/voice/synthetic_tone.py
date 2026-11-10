"""Deterministic tone renderer. This is not speech and not a cloned voice."""

from __future__ import annotations

import math
import struct


def tone_wav(text: str, sample_rate: int = 8000) -> bytes:
    """Render a short sine tone whose pitch depends only on the text."""
    if sample_rate < 1000:
        raise ValueError("sample_rate is too low")
    duration = min(1.2, 0.25 + 0.01 * len(text))
    frequency = 220 + (sum(text.encode("utf-8")) % 440)
    frames = bytearray()
    total = max(1, int(sample_rate * duration))
    for index in range(total):
        sample = int(9000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    data_size = len(frames)
    header = b"".join(
        [
            b"RIFF",
            struct.pack("<I", 36 + data_size),
            b"WAVE",
            b"fmt ",
            struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16),
            b"data",
            struct.pack("<I", data_size),
        ]
    )
    return header + bytes(frames)
