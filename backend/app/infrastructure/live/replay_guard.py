"""Garde anti-rejeu en mémoire — implémente ReplayGuard (LIVE-7.1).

Mono-instance. Pour le multi-worker, fournir une implémentation Redis (SET NX) honorant
le même port.
"""

from __future__ import annotations


class InMemoryReplayGuard:
    def __init__(self) -> None:
        self._consumed: set[str] = set()

    async def try_consume(self, jti: str) -> bool:
        if jti in self._consumed:
            return False
        self._consumed.add(jti)
        return True
