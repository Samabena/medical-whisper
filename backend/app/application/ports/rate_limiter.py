"""Port de limitation de débit (SEC-2.2). In-memory en dev, Redis en prod."""

from __future__ import annotations

from typing import Protocol


class RateLimiter(Protocol):
    async def allow(self, key: str) -> bool:
        """True si la requête est autorisée pour `key` dans la fenêtre courante."""
        ...
