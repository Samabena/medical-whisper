"""Authentification administrateur (SEC-2.1).

Vérifie le mot de passe admin via argon2 (port `PasswordHasher`). On accepte soit un
hash argon2 fourni en config (prod), soit un mot de passe en clair (dev) que l'on hache
une fois en mémoire — dans les deux cas la vérification est constante en temps (argon2).
"""

from __future__ import annotations

from app.application.ports.security import PasswordHasher
from app.domain.errors import UnauthorizedError


class AdminAuthenticator:
    def __init__(self, hasher: PasswordHasher, password_hash: str = "", plaintext: str = "") -> None:
        self._hasher = hasher
        if password_hash:
            self._hash = password_hash
        elif plaintext:
            self._hash = hasher.hash(plaintext)
        else:
            self._hash = ""  # aucun mot de passe configuré → tout refus

    def verify(self, candidate: str) -> bool:
        if not self._hash or not candidate:
            return False
        return self._hasher.verify(self._hash, candidate)

    def authenticate(self, candidate: str) -> None:
        """Lève UnauthorizedError si le mot de passe est incorrect."""
        if not self.verify(candidate):
            raise UnauthorizedError("Mot de passe administrateur incorrect.")
