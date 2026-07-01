"""VOX-6.1 — adapter WhisperLive : unit (conversion audio) + integration (serveur réel)."""

from __future__ import annotations

import pytest

from app.application.ports.stt import SttFinal, SttPartial
from app.infrastructure.stt.whisperlive import WhisperLiveSession, _pcm16_to_float32_bytes


def test_conversion_pcm16_vers_float32():
    # 0, +max, -max en int16 → 0.0, ~1.0, -1.0 en float32 LE (4 octets/échantillon).
    import struct

    frame = struct.pack("<3h", 0, 32767, -32768)
    out = struct.unpack("<3f", _pcm16_to_float32_bytes(frame))
    assert out[0] == 0.0
    assert 0.99 < out[1] <= 1.0
    assert -1.0 <= out[2] < -0.99


async def test_emettre_segment_mappe_partiel_et_final():
    session = WhisperLiveSession.__new__(WhisperLiveSession)  # sans ouvrir de WS
    import asyncio

    session._queue = asyncio.Queue()
    session._closed = False
    session._last_partial = ""

    await session._emettre_segment({"text": "bonjour", "completed": False, "probability": 0.9})
    await session._emettre_segment(
        {
            "text": "bonjour le patient",
            "completed": True,
            "words": [{"word": "bonjour", "probability": 0.95}],
        }
    )
    partiel = session._queue.get_nowait()
    final = session._queue.get_nowait()
    assert isinstance(partiel, SttPartial) and partiel.stable is True
    assert isinstance(final, SttFinal) and final.text == "bonjour le patient"
    assert final.words[0].conf == 0.95


@pytest.mark.integration
async def test_connexion_serveur_reel():
    """Connexion à un vrai serveur WhisperLive (skippé sans serveur)."""
    import os

    url = os.environ.get("WHISPERLIVE_URL")
    if not url:
        pytest.skip("WHISPERLIVE_URL non défini")
    from app.domain.value_objects import Language
    from app.infrastructure.stt.whisperlive import WhisperLiveStream

    stream = WhisperLiveStream(url=url, model="large-v3")
    s = await stream.open(language=Language.FR, hotwords=["dyspnée"])
    await s.close()
