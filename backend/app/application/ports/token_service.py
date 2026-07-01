"""Port du service de jetons éphémères de session (INT-5.1).

Le backend client obtient un jeton court via REST ; le frontend client l'utilise pour
ouvrir le WebSocket live. Le jeton porte l'identifiant de session et une expiration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SessionToken:
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    session_id: str
    jti: str  # identifiant unique du jeton (anti-rejeu, cf. EPIC 7.1)


class EphemeralTokenPort(Protocol):
    def mint(self, session_id: str, ttl_seconds: int) -> SessionToken: ...
    def verify(self, token: str) -> TokenClaims: ...  # lève UnauthorizedError si invalide/expiré
