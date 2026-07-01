"""Port STT streaming (VOX-6.1) — reconnaissance vocale temps réel.

Abstraction du moteur STT (WhisperLive en prod, stub en dev). On **envoie** des trames
audio en continu et on **reçoit** un flux d'événements : partiels (dont « stables »),
fin de parole (endpoint VAD) et finaux validés. Aucune dépendance à FastAPI/réseau ici.

Les drapeaux `stable` (partiel fiable) et l'événement `SttEndpoint` alimentent le
**déclenchement spéculatif** de l'orchestrateur (cf. ARCHITECTURE §5, LIVE-7.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable

from app.domain.value_objects import Language


@dataclass(frozen=True)
class WordConf:
    """Mot reconnu et sa probabilité (signal de confiance exploité par l'extracteur)."""

    word: str
    conf: float


@dataclass(frozen=True)
class SttPartial:
    """Hypothèse intermédiaire. `stable=True` si jugée fiable (seuil de confiance)."""

    text: str
    stable: bool = False


@dataclass(frozen=True)
class SttEndpoint:
    """Fin de parole détectée (VAD endpointing) — avant le final validé."""


@dataclass(frozen=True)
class SttFinal:
    """Transcript validé (LocalAgreement) avec confiance par mot."""

    text: str
    words: list[WordConf] = field(default_factory=list)


# Événements émis par le moteur STT.
SttEvent = SttPartial | SttEndpoint | SttFinal


@runtime_checkable
class SttSession(Protocol):
    """Session STT ouverte (un flux audio en cours)."""

    async def send_audio(self, frame: bytes) -> None:
        """Pousse une trame audio (PCM s16le 16 kHz mono, ou Opus selon l'adapter)."""
        ...

    async def end_turn(self) -> None:
        """Signale une fin de parole (force l'émission d'un endpoint/final)."""
        ...

    def events(self) -> AsyncIterator[SttEvent]:
        """Flux asynchrone des événements (partiels, endpoint, finaux)."""
        ...

    async def close(self) -> None:
        """Ferme la session et libère la connexion."""
        ...


@runtime_checkable
class SttStreamPort(Protocol):
    """Fabrique de sessions STT, conditionnée par la langue et les hotwords du formulaire."""

    async def open(self, *, language: Language, hotwords: list[str]) -> SttSession: ...
