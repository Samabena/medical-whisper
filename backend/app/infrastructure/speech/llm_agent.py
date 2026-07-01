"""Agent vocal conversationnel piloté par un LLM texte — DEV, sans GPU (MODEL-6.4).

Substitut local de PersonaPlex pour tester la *qualité du dialogue* et le rendu sans
GPU : au lieu d'un modèle speech-to-speech, on fait converser un LLM texte (Ollama,
local ou cloud) selon la persona du formulaire. L'utilisateur tape ses répliques
(message `user_text`) ; l'agent répond une question à la fois, dans la langue du compte.

Contrairement au `StubSpeechAgent` (réponses scriptées figées), les réponses sont
générées dynamiquement → utile pour juger le naturel de la persona avant la prod GPU.
L'audio n'est pas synthétisé (le rendu testé est textuel) : `send_audio` est ignoré.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

from app.application.ports.speech_agent import (
    AgentTurnEnd,
    SpeechError,
    SpeechEvent,
    Transcript,
)
from app.domain.value_objects import Language

logger = logging.getLogger(__name__)


def _system_prompt(persona: str, language: Language) -> str:
    """Persona du formulaire + cadrage conversationnel (réponses courtes, une question)."""
    if language is Language.FR:
        cadre = (
            "\n\nTu mènes une conversation parlée, naturelle et chaleureuse. Réponds en "
            "1 à 2 phrases maximum, pose une seule question à la fois et ne récite jamais "
            "tout le formulaire. N'invente aucune donnée. Quand les informations requises "
            "semblent recueillies, remercie brièvement et conclus."
        )
    else:
        cadre = (
            "\n\nYou lead a spoken, natural and warm conversation. Reply in at most 1-2 "
            "sentences, ask a single question at a time and never recite the whole form. "
            "Do not invent any data. Once the required information seems collected, thank "
            "the user briefly and conclude."
        )
    return persona + cadre


@dataclass
class LlmSpeechSession:
    """Session de dialogue texte : historise la conversation et appelle le LLM par tour."""

    client: object  # ollama.AsyncClient
    model: str
    persona: str
    language: Language
    received_frames: list[bytes] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._queue: asyncio.Queue[SpeechEvent | None] = asyncio.Queue()
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": _system_prompt(self.persona, self.language)}
        ]
        self._closed = False

    async def _repondre(self, user_text: str | None) -> None:
        """Ajoute éventuellement le tour utilisateur, interroge le LLM, émet la réponse agent."""
        if user_text is not None:
            self._messages.append({"role": "user", "content": user_text})
        try:
            resp = await self.client.chat(  # type: ignore[attr-defined]
                model=self.model,
                messages=self._messages,
                options={"temperature": 0.6},
            )
            texte = resp["message"]["content"].strip()
        except Exception as exc:  # noqa: BLE001 — l'agent ne doit pas casser le relais live
            logger.warning("Agent LLM (%s) en échec : %s", self.model, exc)
            await self._queue.put(SpeechError(f"Agent LLM indisponible : {exc}"))
            return
        self._messages.append({"role": "assistant", "content": texte})
        await self._queue.put(Transcript(texte, "agent", is_final=True))
        await self._queue.put(AgentTurnEnd())

    async def _ouvrir(self) -> None:
        """Tour d'ouverture : l'agent salue et pose sa première question (sans tour user)."""
        amorce = (
            "Commence la conversation : salue brièvement et pose ta première question."
            if self.language is Language.FR
            else "Start the conversation: greet briefly and ask your first question."
        )
        await self._repondre(amorce)
        # L'amorce est une consigne interne, pas un vrai tour utilisateur : on la retire
        # de l'historique pour ne pas polluer le contexte des tours suivants.
        self._messages = [m for m in self._messages if m["content"] != amorce]

    async def send_audio(self, frame: bytes) -> None:
        self.received_frames.append(frame)  # pas de STT en dev : audio ignoré

    async def send_user_text(self, text: str) -> None:
        if self._closed or not text.strip():
            return
        await self._repondre(text)

    async def end_user_turn(self) -> None:
        # Pilotage par texte (`user_text`) : la fin de tour micro n'a pas de sens ici.
        return

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
class LlmSpeechAgent:
    """Fabrique de sessions conversationnelles LLM (dev). Réutilise le client Ollama."""

    host: str
    model: str
    api_key: str | None = None

    def __post_init__(self) -> None:
        from ollama import AsyncClient

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        self._client = AsyncClient(host=self.host, headers=headers)

    async def open(
        self,
        *,
        persona: str,
        voice: str,
        language: Language,
        hotwords: list[str] | None = None,  # ignoré : agent texte sans STT
    ) -> LlmSpeechSession:
        session = LlmSpeechSession(
            client=self._client, model=self.model, persona=persona, language=language
        )
        await session._ouvrir()
        return session
