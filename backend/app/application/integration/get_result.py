"""Récupération du résultat d'une session (INT-5.2, server-to-server)."""

from __future__ import annotations

from app.application.ports.repositories import SessionRepo
from app.application.ports.result_store import SessionResultStore
from app.domain.entities import Account
from app.domain.errors import NotFoundError


class GetSessionResult:
    def __init__(self, sessions: SessionRepo, results: SessionResultStore) -> None:
        self._sessions = sessions
        self._results = results

    async def execute(self, account: Account, session_id: str) -> dict:
        session = await self._sessions.get(session_id)
        if session is None or session.account_id != account.id:
            # Même réponse pour « inconnue » et « pas à vous » : pas de fuite d'existence.
            raise NotFoundError(f"Session {session_id!r} introuvable.")
        result = await self._results.get(session_id)
        if result is None:
            raise NotFoundError("Résultat indisponible — session non terminée ou expirée.")
        return result
