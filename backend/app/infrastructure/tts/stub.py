"""TTS stub — DEV/test (VOX-6.3).

Produit un WAV **valide** (RIFF/WAVE, PCM s16le 16 kHz mono) de silence, d'une durée
proportionnelle à la longueur du texte. Déterministe, sans dépendance externe : permet
de tester tout le pipeline (segmentation par phrase, envoi audio, barge-in) sans Piper.
"""

from __future__ import annotations

import struct
from typing import AsyncIterator

from app.application.ports.tts import TTS_SAMPLE_RATE

SAMPLE_RATE = 16_000
_BYTES_PAR_CAR = 800  # ~25 ms de silence par caractère (durée plausible)


def _wav_silence(n_samples: int) -> bytes:
    """Encode `n_samples` échantillons de silence en WAV PCM s16le mono 16 kHz."""
    data = b"\x00\x00" * n_samples
    block_align = 2  # mono * 16 bits
    byte_rate = SAMPLE_RATE * block_align
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE, byte_rate, block_align, 16)
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )


class StubTts:
    """Synthèse factice : un WAV de silence dimensionné sur le texte."""

    async def synthetiser(self, texte: str, voix: str) -> bytes:
        n_samples = max(1, len(texte.strip())) * (_BYTES_PAR_CAR // 2)
        return _wav_silence(n_samples)

    async def stream(self, texte: str, voix: str) -> AsyncIterator[bytes]:
        """Émet du PCM s16le silencieux @ TTS_SAMPLE_RATE en plusieurs chunks (mode live)."""
        n_samples = max(1, len(texte.strip())) * (_BYTES_PAR_CAR // 2)
        # Durée équivalente au débit de synthetiser, rééchelonnée au taux du contrat streaming.
        n_samples = int(n_samples * TTS_SAMPLE_RATE / SAMPLE_RATE)
        pcm = b"\x00\x00" * n_samples
        step = 4096  # ~93 ms/chunk @ 22050 — simule un flux progressif
        for i in range(0, len(pcm), step):
            yield pcm[i : i + step]
