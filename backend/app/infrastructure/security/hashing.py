"""Implémentation du port `KeyHasher` (SHA-256, cohérent avec api_keys.hacher)."""

from __future__ import annotations

from app.infrastructure.security.api_keys import hacher


class Sha256KeyHasher:
    def hash(self, raw: str) -> str:
        return hacher(raw)
