"""Abstraction de la connexion client (LIVE-7.2).

L'orchestrateur raisonne sur ce port, pas sur le WebSocket Starlette → testable avec un
faux canal en mémoire. La couche `interface` fournit l'adapter WebSocket réel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AudioFrame:
    """Trame audio entrante du client (micro)."""

    data: bytes


@dataclass(frozen=True)
class Control:
    """Message de contrôle JSON entrant (ex. {"type": "end_turn"})."""

    payload: dict


@dataclass(frozen=True)
class Closed:
    """Le client a fermé la connexion."""


ClientMessage = AudioFrame | Control | Closed


class ClientConnection(Protocol):
    async def receive(self) -> ClientMessage: ...
    async def send_audio(self, data: bytes) -> None: ...
    async def send_json(self, msg: dict) -> None: ...
    async def close(self, code: int = 1000) -> None: ...
