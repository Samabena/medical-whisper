"""Store de résultats en mémoire avec rétention courte (OBS-10.1 / INT-5.2).

Le formulaire final est une **donnée de santé** : il n'est conservé que le temps que le
backend client le récupère (TTL court, purge paresseuse), puis effacé. Aucun audio ni
transcript n'y est stocké. Pour le multi-instance, fournir une impl Redis (même port).
"""

from __future__ import annotations

import time


class InMemorySessionResultStore:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl = ttl_seconds
        self._items: dict[str, tuple[dict, float]] = {}

    async def save(self, session_id: str, result: dict) -> None:
        self._items[session_id] = (result, time.time() + self._ttl)

    async def get(self, session_id: str) -> dict | None:
        item = self._items.get(session_id)
        if item is None:
            return None
        result, expiry = item
        if time.time() > expiry:
            del self._items[session_id]  # purge paresseuse des données de santé
            return None
        return result
