"""Configuration 12-factor (CORE-0.2).

Tous les réglages proviennent de l'environnement (`.env` en dev, secrets en prod).
Les secrets (`jwt_secret`, `admin_password`) sont **obligatoires** : leur absence
provoque une erreur explicite au démarrage plutôt qu'un défaut non sûr.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Persistance -------------------------------------------------------
    database_url: str = "postgresql+asyncpg://vtf:vtf@db:5432/voicetoform"
    redis_url: str = "redis://redis:6379/0"

    # --- Modèle live (PersonaPlex) ----------------------------------------
    # stub        : agent vocal scripté, AUCUN GPU requis (dev).
    # personaplex : adapter WebSocket vers le serveur Moshi/PersonaPlex (prod, GPU).
    speech_agent: Literal["stub", "personaplex"] = "stub"
    model_ws_url: str = "ws://model:8998/api/chat"

    # --- Sécurité (OBLIGATOIRES, pas de défaut) ---------------------------
    jwt_secret: str
    admin_email: str = "admin@local"
    admin_password: str

    # --- Divers ------------------------------------------------------------
    default_language: Literal["en", "fr"] = "fr"
    cors_origins: list[str] = []
    session_token_ttl_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    """Singleton caché des réglages (instancié une seule fois)."""
    return Settings()
