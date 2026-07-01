"""Adapter PersonaPlex — client WebSocket vers le serveur Moshi/PersonaPlex (MODEL-6.3).

Implémente `SpeechAgentPort` en prod (GPU). Ouvre une connexion WS par session, envoie
l'init (persona+voix+langue), relaie l'audio et décode les événements via `protocol.py`.

Envoi et réception sont concurrents : `events()` itère la connexion pendant que
`send_audio()` y écrit — supporté par la lib `websockets`.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

import websockets

from app.application.ports.speech_agent import SpeechError, SpeechEvent
from app.domain.value_objects import Language
from app.infrastructure.speech.protocol import (
    decode_message,
    encode_end_turn,
    encode_init,
)

logger = logging.getLogger(__name__)


class PersonaPlexSession:
    def __init__(self, ws: websockets.WebSocketClientProtocol) -> None:
        self._ws = ws

    async def send_audio(self, frame: bytes) -> None:
        await self._ws.send(frame)

    async def end_user_turn(self) -> None:
        await self._ws.send(encode_end_turn())

    async def events(self) -> AsyncIterator[SpeechEvent]:
        try:
            async for raw in self._ws:
                ev = decode_message(raw)
                if ev is not None:
                    yield ev
        except websockets.ConnectionClosed:
            return
        except Exception as exc:  # remonte proprement au lieu de planter le relais
            logger.warning("Erreur de réception PersonaPlex : %s", exc)
            yield SpeechError(str(exc))

    async def close(self) -> None:
        await self._ws.close()


class PersonaPlexClient:
    """Fabrique de sessions PersonaPlex (prod)."""

    def __init__(self, ws_url: str) -> None:
        self._url = ws_url

    async def open(
        self,
        *,
        persona: str,
        voice: str,
        language: Language,
        hotwords: list[str] | None = None,  # ignoré : S2S sans STT séparé
    ) -> PersonaPlexSession:
        ws = await websockets.connect(self._url, max_size=None)
        await ws.send(encode_init(persona, voice, language))
        logger.info("Session PersonaPlex ouverte (langue=%s).", language.value)
        return PersonaPlexSession(ws)
