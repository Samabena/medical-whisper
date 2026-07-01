"""Port de stockage du résultat d'une session (INT-5.2).

Le formulaire final (produit par l'extraction, EPIC 8) est déposé ici à la clôture, puis
récupéré par le backend client en server-to-server. Rétention courte, AUCUN audio.
"""

from __future__ import annotations

from typing import Protocol


class SessionResultStore(Protocol):
    async def save(self, session_id: str, result: dict) -> None: ...
    async def get(self, session_id: str) -> dict | None: ...
