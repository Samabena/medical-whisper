"""Port des jetons de session admin (SEC-2.1) — paire access (court) + refresh (long)."""

from __future__ import annotations

from typing import Protocol


class AdminTokenService(Protocol):
    def issue_pair(self, subject: str) -> tuple[str, str]:
        """Retourne (access_token, refresh_token)."""
        ...

    def refresh(self, refresh_token: str) -> str:
        """Échange un refresh valide contre un nouvel access. Lève UnauthorizedError sinon."""
        ...

    def verify_access(self, token: str) -> str:
        """Retourne le sujet (email admin) si l'access est valide. Lève UnauthorizedError sinon."""
        ...
