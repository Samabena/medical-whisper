"""Hachage de mots de passe via argon2 (implémente PasswordHasher, SEC-2.1)."""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import Argon2Error, VerifyMismatchError


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._ph = _Argon2()

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, hashed: str, password: str) -> bool:
        try:
            return self._ph.verify(hashed, password)
        except (VerifyMismatchError, Argon2Error, ValueError):
            return False
