"""Agent vocal **sandwich** (v3) — composition STT → agent + TTS (LIVE-7.2 / VOX-6).

Implémente le port `SpeechAgentPort` en **composant** trois briques derrière leurs ports :
- `SttStreamPort` : audio → transcripts (partiels stables, endpoint, finaux) ;
- `ReplyProvider` : tour utilisateur → réplique de l'agent **en streaming** ;
- `TtsPort` : réplique (découpée **par phrase** via le segmenteur) → audio.

Le sandwich expose exactement la même interface `SpeechSession` que l'ancien agent S2S :
l'orchestrateur (`RunLiveDialogue`) et tout son câblage latence (spéculatif, backchannel,
barge-in) fonctionnent **sans modification**. L'extraction du formulaire reste dans
l'orchestrateur (`FormExtractorPort`), nourrie par les transcripts utilisateur émis ici.

Mapping des événements émis vers l'orchestrateur :
- `SttPartial(stable)` → `Transcript(user, stable=True)`  (déclenchement spéculatif) ;
- `SttEndpoint`        → `SpeechEndpoint`                  (backchannel + spéculatif) ;
- `SttFinal`           → `Transcript(user, final)` puis la réplique agent (texte + audio).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

from app.application.live.segmenter import aiter_sentences
from app.application.ports.speech_agent import (
    AgentTurnEnd,
    AudioChunk,
    SpeechEndpoint,
    SpeechError,
    SpeechEvent,
    Transcript,
)
from app.application.ports.stt import SttEndpoint, SttFinal, SttPartial, SttSession, SttStreamPort
from app.application.ports.tts import TtsPort
from app.domain.value_objects import Language
from app.infrastructure.speech.reply import ReplyProvider

logger = logging.getLogger(__name__)

ReplyFactory = Callable[[str, Language], ReplyProvider]

# Symboles/markdown que le TTS prononcerait littéralement (« arobase », « dièse »…).
_EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff←-⇿⌀-⏿]"
)
_SYMBOLS = re.compile(r"[*_#`~|<>^=+@&{}\[\]\\/]+")


def clean_for_tts(text: str) -> str:
    """Nettoie une réplique avant synthèse vocale : retire émojis, markdown et symboles
    que Piper lirait à voix haute (@, #, *, …), normalise les espaces."""
    t = _EMOJI.sub("", text)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)  # puces de liste
    t = _SYMBOLS.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


@dataclass
class SandwichSpeechSession:
    """Session sandwich : pont STT ↔ (agent + TTS), exposé comme `SpeechSession`."""

    stt: SttSession
    tts: TtsPort
    reply: ReplyProvider
    voice: str
    language: Language
    clause_min_chars: int = 60  # segmentation fine (clauses) pour le 1er son ; 0 = phrases seules

    def __post_init__(self) -> None:
        self._out: asyncio.Queue[SpeechEvent | None] = asyncio.Queue()
        self._reply_lock = asyncio.Lock()
        self._closed = False
        self._pump = asyncio.create_task(self._pump_stt())
        self._opening = asyncio.create_task(self._dire(self.reply.opening()))

    async def _dire(self, source: AsyncIterator[str]) -> None:
        """Synthétise une réplique agent **par phrase/clause**, en STREAMING (TTS pipeliné).

        Chaque phrase est synthétisée en flux : ses chunks PCM sont relayés au fil de l'eau
        (plusieurs `AudioChunk` par phrase) → premier son plus tôt et lecture gapless côté
        navigateur. La segmentation fine (clauses) réduit encore la latence du 1er son."""
        async with self._reply_lock:
            async for phrase in aiter_sentences(source, clause_min_chars=self.clause_min_chars):
                if self._closed:
                    return
                parle = clean_for_tts(phrase)  # texte « parlable » (sans @, #, *, émojis…)
                if not parle:
                    continue  # phrase = uniquement des symboles : rien à dire
                await self._out.put(Transcript(parle, "agent", is_final=False))
                try:
                    async for pcm in self.tts.stream(parle, self.voice):
                        if self._closed:
                            return
                        if pcm:
                            await self._out.put(AudioChunk(pcm))
                except Exception as exc:  # noqa: BLE001 — le TTS ne doit pas casser le relais
                    # %r expose le TYPE même quand str(exc) est vide (ex. NotImplementedError
                    # de create_subprocess_exec sous SelectorEventLoop : uvicorn --reload sur Windows).
                    logger.warning("TTS en échec : %r", exc)
                    continue
            await self._out.put(AgentTurnEnd())

    async def _pump_stt(self) -> None:
        try:
            async for ev in self.stt.events():
                if isinstance(ev, SttPartial):
                    if ev.stable and ev.text.strip():
                        await self._out.put(Transcript(ev.text, "user", stable=True))
                elif isinstance(ev, SttEndpoint):
                    await self._out.put(SpeechEndpoint())
                elif isinstance(ev, SttFinal):
                    if ev.text.strip():
                        await self._out.put(Transcript(ev.text, "user", is_final=True))
                        await self._dire(self.reply.reply(ev.text))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            await self._out.put(SpeechError(str(exc)))
        finally:
            await self._out.put(None)

    # --- Interface SpeechSession --------------------------------------------
    async def send_audio(self, frame: bytes) -> None:
        await self.stt.send_audio(frame)

    async def end_user_turn(self) -> None:
        await self.stt.end_turn()

    async def events(self) -> AsyncIterator[SpeechEvent]:
        while True:
            ev = await self._out.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        self._closed = True
        for tache in (self._pump, self._opening):
            if not tache.done():
                tache.cancel()
        await asyncio.gather(self._pump, self._opening, return_exceptions=True)
        await self.stt.close()
        await self._out.put(None)


@dataclass
class SandwichSpeechAgent:
    """Fabrique d'agents sandwich. Compose STT + TTS + fabrique de `ReplyProvider`."""

    stt_stream: SttStreamPort
    tts: TtsPort
    reply_factory: ReplyFactory
    hotwords: list[str] = field(default_factory=list)  # repli si la session n'en fournit pas
    clause_min_chars: int = 60  # segmentation fine (clauses) pour réduire la latence du 1er son

    async def open(
        self,
        *,
        persona: str,
        voice: str,
        language: Language,
        hotwords: list[str] | None = None,
    ) -> SandwichSpeechSession:
        # Hotwords du formulaire (par session) prioritaires ; sinon repli sur ceux de l'agent.
        mots = list(hotwords) if hotwords else self.hotwords
        stt = await self.stt_stream.open(language=language, hotwords=mots)
        reply = self.reply_factory(persona, language)
        return SandwichSpeechSession(
            stt=stt,
            tts=self.tts,
            reply=reply,
            voice=voice,
            language=language,
            clause_min_chars=self.clause_min_chars,
        )
