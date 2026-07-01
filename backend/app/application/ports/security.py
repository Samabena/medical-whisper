"""Ports de sécurité — hachage (l'algorithme reste un détail d'infrastructure)."""

from __future__ import annotations

from typing import Protocol


class KeyHasher(Protocol):
    """Hache une clé API en clair pour la comparer au hash stocké."""

    def hash(self, raw: str) -> str: ...


class PasswordHasher(Protocol):
    """Hachage/vérification de mots de passe humains (argon2, anti-bruteforce)."""

    def hash(self, password: str) -> str: ...
    def verify(self, hashed: str, password: str) -> bool: ...
