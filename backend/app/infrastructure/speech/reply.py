"""Fournisseurs de réponse de l'agent conversationnel (composant du sandwich, VOX-6.4).

L'agent du sandwich = la partie « dialogue » : à partir du tour utilisateur (texte issu
du STT), il produit la réplique de l'agent, **en streaming** (token par token) pour
alimenter le segmenteur → TTS sans attendre toute la réponse.

Deux implémentations :
- `ScriptedReply` : réponses figées (dev/test, sans LLM) ;
- `OllamaStreamingReply` : réponses générées en flux par un LLM texte (Ollama), persona
  du formulaire, réponses courtes (une question à la fois).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable

from app.domain.value_objects import Language

logger = logging.getLogger(__name__)


@runtime_checkable
class ReplyProvider(Protocol):
    """Génère, en flux, l'ouverture puis les répliques de l'agent."""

    def opening(self) -> AsyncIterator[str]: ...
    def reply(self, user_text: str) -> AsyncIterator[str]: ...


def _cadre_systeme(persona: str, language: Language) -> str:
    if language is Language.FR:
        cadre = (
            "\n\nTu mènes une conversation parlée, naturelle et chaleureuse. Réponds en "
            "1 à 2 phrases maximum, pose une seule question à la fois et ne récite jamais "
            "tout le formulaire. N'invente aucune donnée. Quand les informations requises "
            "semblent recueillies, remercie brièvement et conclus."
            "\n\nIMPORTANT : ta réponse est lue à voix haute. Écris UNIQUEMENT du texte "
            "parlé en français, sans aucun symbole, markdown, puce, dièse, astérisque, "
            "arobase, émoji ni mise en forme. Écris les nombres et unités en toutes lettres "
            "si possible. Une seule phrase parlée, prête à être prononcée."
        )
    else:
        cadre = (
            "\n\nYou lead a spoken, natural and warm conversation. Reply in at most 1-2 "
            "sentences, ask a single question at a time and never recite the whole form. "
            "Do not invent any data. Once the required information seems collected, thank "
            "the user briefly and conclude."
            "\n\nIMPORTANT: your reply is read aloud. Write ONLY spoken text, with no "
            "symbols, markdown, bullets, hashes, asterisks, at-signs, emojis or formatting. "
            "A single spoken sentence, ready to be pronounced."
        )
    return persona + cadre


@dataclass
class ScriptedReply:
    """Réponses scriptées déterministes (dev/test). `greeting` ouvre la conversation."""

    replies: list[str] = field(default_factory=list)
    greeting: str = "Bonjour, je vous écoute."

    def __post_init__(self) -> None:
        self._idx = 0

    async def opening(self) -> AsyncIterator[str]:
        yield self.greeting

    async def reply(self, user_text: str) -> AsyncIterator[str]:
        if self._idx < len(self.replies):
            texte = self.replies[self._idx]
            self._idx += 1
        else:
            texte = "Très bien."
        yield texte


@dataclass
class OllamaStreamingReply:
    """Agent conversationnel LLM en streaming (Ollama). Réutilise le client async."""

    host: str
    model: str
    persona: str
    language: Language
    api_key: str | None = None
    max_tokens: int = 120

    def __post_init__(self) -> None:
        from ollama import AsyncClient

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else None
        self._client = AsyncClient(host=self.host, headers=headers)
        self._messages: list[dict[str, str]] = [
            {"role": "system", "content": _cadre_systeme(self.persona, self.language)}
        ]

    async def _stream(self, consigne: str) -> AsyncIterator[str]:
        self._messages.append({"role": "user", "content": consigne})
        morceaux: list[str] = []
        try:
            async for part in await self._client.chat(
                model=self.model,
                messages=self._messages,
                stream=True,
                options={"temperature": 0.6, "num_predict": self.max_tokens},
            ):
                bout = part.get("message", {}).get("content", "")
                if bout:
                    morceaux.append(bout)
                    yield bout
        except Exception as exc:  # noqa: BLE001 — l'agent ne doit pas casser le relais live
            logger.warning("Agent LLM (%s) en échec : %s", self.model, exc)
            return
        self._messages.append({"role": "assistant", "content": "".join(morceaux)})

    async def opening(self) -> AsyncIterator[str]:
        amorce = (
            "Commence la conversation : salue brièvement et pose ta première question."
            if self.language is Language.FR
            else "Start the conversation: greet briefly and ask your first question."
        )
        async for bout in self._stream(amorce):
            yield bout
        # L'amorce est une consigne interne : on la retire de l'historique.
        self._messages = [m for m in self._messages if m["content"] != amorce]

    async def reply(self, user_text: str) -> AsyncIterator[str]:
        async for bout in self._stream(user_text):
            yield bout
