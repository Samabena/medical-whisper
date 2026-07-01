"""STT stub — DEV, AUCUN GPU requis (VOX-6.2).

Transcripts **scriptés déterministes** : à chaque fin de parole (`end_turn`), le stub
émet, pour l'énoncé courant, la séquence réaliste *partiel stable → endpoint → final*.
Permet de tester tout le pipeline sandwich (STT → agent → TTS) et le déclenchement
spéculatif sans le serveur WhisperLive.

Le scénario (liste d'énoncés utilisateur) est injectable ; à court d'énoncés, `end_turn`
émet un final vide (l'agent acquiescera).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.application.ports.stt import (
    SttEndpoint,
    SttEvent,
    SttFinal,
    SttPartial,
    WordConf,
)
from app.domain.value_objects import Language


@dataclass
class StubSttSession:
    """Session STT scriptée : `end_turn` débite l'énoncé suivant."""

    utterances: list[str] = field(default_factory=list)
    received_frames: list[bytes] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._queue: asyncio.Queue[SttEvent | None] = asyncio.Queue()
        self._idx = 0
        self._closed = False

    async def send_audio(self, frame: bytes) -> None:
        self.received_frames.append(frame)

    async def end_turn(self) -> None:
        if self._closed:
            return
        texte = self.utterances[self._idx] if self._idx < len(self.utterances) else ""
        self._idx += 1
        if texte:
            await self._queue.put(SttPartial(texte, stable=True))
        await self._queue.put(SttEndpoint())
        mots = [WordConf(m, 0.95) for m in texte.split()]
        await self._queue.put(SttFinal(texte, mots))

    async def events(self):
        while True:
            ev = await self._queue.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        self._closed = True
        await self._queue.put(None)


@dataclass
class StubSttStream:
    """Fabrique de sessions STT stub. Un scénario optionnel pilote les transcripts."""

    utterances: list[str] = field(default_factory=list)
    last_language: Language | None = None  # dernière langue reçue (introspection en test)
    last_hotwords: list[str] = field(default_factory=list)  # derniers hotwords reçus

    async def open(self, *, language: Language, hotwords: list[str]) -> StubSttSession:
        self.last_language = language
        self.last_hotwords = list(hotwords)
        return StubSttSession(utterances=list(self.utterances))
