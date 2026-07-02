"""Port de l'agent vocal full-duplex (MODEL-6.1).

Abstraction de l'agent vocal (sandwich STT+agent+TTS en prod, stub en dev). Les cas
d'usage `live` dépendent de cette interface, jamais de l'implémentation concrète (DIP).

Contrat full-duplex : on **envoie** des trames audio utilisateur en continu et on
**reçoit** un flux d'événements (audio de l'agent, transcripts, fin de tour) — les deux
sens étant concurrents. Aucune dépendance à FastAPI, SQLAlchemy ou au réseau ici.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Literal, Protocol, runtime_checkable

from app.domain.value_objects import Language

# Format audio d'échange (24 kHz mono capté par le front). L'adapter gère le codec réel
# et le rééchantillonnage vers le STT ; le port raisonne en trames d'octets.
SAMPLE_RATE = 24_000
CHANNELS = 1

Speaker = Literal["user", "agent"]


@dataclass(frozen=True)
class AudioChunk:
    """Audio produit par l'agent, à rejouer au client (PCM/Opus 24 kHz)."""

    data: bytes


@dataclass(frozen=True)
class Transcript:
    """Texte reconnu (user) ou généré (agent). Alimente l'extracteur (EPIC 8).

    `stable` marque un partiel jugé fiable (confiance ≥ seuil) sur lequel le
    déclenchement **spéculatif** peut agir sans attendre le final (LIVE-7.4).
    """

    text: str
    speaker: Speaker
    is_final: bool = False
    stable: bool = False


@dataclass(frozen=True)
class SpeechEndpoint:
    """Fin de parole utilisateur détectée (VAD endpointing).

    Émis **avant** le transcript final validé : permet à l'orchestrateur de lancer
    l'agent en spéculatif sur le meilleur partiel stable (gain ~1–2 s). Cf. ARCHITECTURE §5.
    """


@dataclass(frozen=True)
class Backchannel:
    """Court accusé de réception (« d'accord… ») à jouer immédiatement (LIVE-7.4).

    Masque la latence de réflexion de l'agent. `audio` est optionnel : si absent,
    le client peut se contenter de `text`.
    """

    text: str
    audio: bytes | None = None


@dataclass(frozen=True)
class AgentTurnEnd:
    """L'agent a fini de parler — le client peut reprendre la parole."""


@dataclass(frozen=True)
class SpeechError:
    """Erreur côté modèle."""

    message: str


# Événements émis par le modèle vers le client.
SpeechEvent = (
    AudioChunk | Transcript | SpeechEndpoint | Backchannel | AgentTurnEnd | SpeechError
)


@runtime_checkable
class SpeechSession(Protocol):
    """Session de dialogue ouverte avec le modèle (full-duplex)."""

    async def send_audio(self, frame: bytes) -> None:
        """Envoie une trame audio utilisateur au modèle."""
        ...

    async def end_user_turn(self) -> None:
        """Signale que l'utilisateur a fini de parler (aide au turn-taking)."""
        ...

    def events(self) -> AsyncIterator[SpeechEvent]:
        """Flux asynchrone des événements du modèle (audio, transcript, fin de tour)."""
        ...

    async def close(self) -> None:
        """Ferme la session et libère la connexion."""
        ...


@runtime_checkable
class TextDrivenSession(Protocol):
    """Session acceptant des tours utilisateur en TEXTE (dev sans STT/GPU).

    L'orchestrateur détecte cette capacité (isinstance) pour transmettre les répliques
    tapées (`user_text`) à l'agent afin qu'il génère une réponse conversationnelle. Les
    agents pilotés par l'audio (stub) ne l'implémentent pas.
    """

    async def send_user_text(self, text: str) -> None:
        ...


@runtime_checkable
class SpeechAgentPort(Protocol):
    """Fabrique de sessions de dialogue, conditionnée par la persona/voix/langue.

    `hotwords` (optionnel) = lexique du formulaire transmis au STT pour biaiser la
    reconnaissance (FORM-4.2). Les agents sans STT (stub) l'ignorent.
    """

    async def open(
        self,
        *,
        persona: str,
        voice: str,
        language: Language,
        hotwords: list[str] | None = None,
    ) -> SpeechSession:
        ...
