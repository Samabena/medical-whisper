"""Port anti-rejeu des jetons de session (usage unique).

In-memory en mono-instance ; à implémenter sur Redis pour le multi-worker (LIVE-7.3).
"""

from __future__ import annotations

from typing import Protocol


class ReplayGuard(Protocol):
    async def try_consume(self, jti: str) -> bool:
        """Retourne True au premier usage d'un `jti`, False s'il a déjà été consommé."""
        ...
