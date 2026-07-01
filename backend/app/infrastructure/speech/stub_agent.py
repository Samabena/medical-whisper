"""Agent vocal scripté — DEV, AUCUN GPU requis (MODEL-6.2).

Simule un dialogue full-duplex déterministe : à chaque fin de tour utilisateur, le stub
émet un transcript utilisateur scripté puis une réponse de l'agent (transcript + audio
factice). Permet de développer et tester TOUT le pipeline live (EPIC 7) et l'extraction
(EPIC 8) sans le modèle réel.

Le scénario est injectable ; sans scénario, l'agent salue puis acquiesce génériquement.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator

from app.application.ports.speech_agent import (
    AgentTurnEnd,
    AudioChunk,
    SpeechEvent,
    Transcript,
)
from app.domain.value_objects import Language

# 10 ms de silence PCM16 mono 24 kHz — substitut d'audio (le stub ne synthétise pas).
_SILENCE = b"\x00\x00" * 240


@dataclass
class ScriptedTurn:
    """Un échange scripté : ce que « dit » l'utilisateur, ce que répond l'agent."""

    user_text: str
    agent_text: str


@dataclass
class StubSpeechSession:
    persona: str
    language: Language
    script: list[ScriptedTurn] = field(default_factory=list)
    received_frames: list[bytes] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._queue: asyncio.Queue[SpeechEvent | None] = asyncio.Queue()
        self._idx = 0
        self._closed = False

    async def _emettre_ouverture(self) -> None:
        salutation = "Bonjour, je vous écoute." if self.language is Language.FR else "Hello, I'm listening."
        await self._queue.put(Transcript(salutation, "agent", is_final=True))
        await self._queue.put(AudioChunk(_SILENCE))
        await self._queue.put(AgentTurnEnd())

    async def send_audio(self, frame: bytes) -> None:
        self.received_frames.append(frame)

    async def end_user_turn(self) -> None:
        if self._closed:
            return
        if self._idx < len(self.script):
            tour = self.script[self._idx]
            self._idx += 1
            await self._queue.put(Transcript(tour.user_text, "user", is_final=True))
            await self._queue.put(Transcript(tour.agent_text, "agent", is_final=True))
            await self._queue.put(AudioChunk(_SILENCE))
        else:
            # Hors script : l'utilisateur a parlé mais rien n'est prévu — l'agent acquiesce.
            accuse = "Très bien." if self.language is Language.FR else "All right."
            await self._queue.put(Transcript("", "user", is_final=True))
            await self._queue.put(Transcript(accuse, "agent", is_final=True))
        await self._queue.put(AgentTurnEnd())

    async def events(self) -> AsyncIterator[SpeechEvent]:
        while True:
            ev = await self._queue.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        self._closed = True
        await self._queue.put(None)


@dataclass
class StubSpeechAgent:
    """Fabrique de sessions stub. Un scénario optionnel pilote le dialogue (tests)."""

    script: list[ScriptedTurn] = field(default_factory=list)

    async def open(
        self,
        *,
        persona: str,
        voice: str,
        language: Language,
        hotwords: list[str] | None = None,  # ignoré : stub sans STT
    ) -> StubSpeechSession:
        session = StubSpeechSession(persona=persona, language=language, script=list(self.script))
        await session._emettre_ouverture()
        return session
