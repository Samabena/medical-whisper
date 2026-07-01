"""Rate-limiter en mémoire (fenêtre fixe par minute) — implémente RateLimiter (SEC-2.2).

Mono-instance. En prod multi-worker, fournir une implémentation Redis (INCR + EXPIRE)
honorant le même port.
"""

from __future__ import annotations

import time


class InMemoryRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self._limit = limit
        self._window = window_seconds
        self._buckets: dict[tuple[str, int], int] = {}

    async def allow(self, key: str) -> bool:
        fenetre = int(time.time() // self._window)
        # Purge paresseuse des fenêtres passées.
        if len(self._buckets) > 10_000:
            self._buckets = {k: v for k, v in self._buckets.items() if k[1] >= fenetre}
        compteur = self._buckets.get((key, fenetre), 0)
        if compteur >= self._limit:
            return False
        self._buckets[(key, fenetre)] = compteur + 1
        return True
