"""STT WhisperLive distant (serveur équipe) — open() query string + encodage audio."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.value_objects import Language
from app.infrastructure.stt.whisperlive import WhisperLiveSession
from app.infrastructure.stt.whisperlive_remote import WhisperLiveRemoteStream


class _FakeWS:
    """WebSocket factice : collecte les envois, flux entrant vide (pas de segments)."""

    def __init__(self) -> None:
        self.sent: list = []
        self.closed = False

    async def send(self, data) -> None:
        self.sent.append(data)

    async def close(self) -> None:
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


async def test_open_passe_la_config_en_query_string():
    fake = _FakeWS()
    with patch("websockets.connect", new=AsyncMock(return_value=fake)) as connect:
        stream = WhisperLiveRemoteStream(
            url="ws://srv-team-ia:9300/v1/audio/live", input_rate=24000
        )
        session = await stream.open(language=Language.FR, hotwords=["dyspnée"])

    url = connect.call_args.args[0]
    assert url.startswith("ws://srv-team-ia:9300/v1/audio/live?")
    assert "language=fr" in url
    assert "sample_rate=16000" in url
    # Audio PCM brut par défaut, et pas de handshake JSON (aucun envoi à l'ouverture).
    assert session.audio_format == "pcm_s16le"
    assert fake.sent == []
    await session.close()


async def test_session_pcm_s16le_envoie_octets_bruts():
    """audio_format=pcm_s16le ⇒ on transmet le PCM tel quel (pas de conversion float32)."""
    fake = _FakeWS()
    session = WhisperLiveSession(ws=fake, input_rate=16000, audio_format="pcm_s16le")
    frame = struct.pack("<2h", 100, -100)
    await session.send_audio(frame)
    assert fake.sent == [frame]
    await session.close()


async def test_session_float32_par_defaut_convertit():
    """Par défaut (WhisperLive standard) ⇒ conversion en float32 (4 octets/échantillon)."""
    fake = _FakeWS()
    session = WhisperLiveSession(ws=fake, input_rate=16000)  # audio_format=float32
    frame = struct.pack("<1h", 32767)  # 1 échantillon s16le
    await session.send_audio(frame)
    assert len(fake.sent[0]) == 4
    await session.close()


@pytest.mark.integration
async def test_serveur_reel():
    """Connexion au vrai endpoint live (skippé sans URL)."""
    import os

    url = os.environ.get("WHISPERLIVE_REMOTE_URL")
    if not url:
        pytest.skip("WHISPERLIVE_REMOTE_URL non défini")
    stream = WhisperLiveRemoteStream(url=url)
    session = await stream.open(language=Language.FR, hotwords=[])
    await session.close()
