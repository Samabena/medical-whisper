"""CORE-0.2 / SEC-2.1 — validation de la configuration (secret requis, longueur, défauts)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def test_jwt_secret_manquant_leve_erreur_claire(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    from app.infrastructure.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)  # ignore .env : on teste l'absence pure
    assert "jwt_secret" in str(exc.value)


def test_jwt_secret_trop_court_refuse(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "trop-court")

    from app.infrastructure.config import Settings

    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    assert "32" in str(exc.value)


def test_valeurs_par_defaut_saines(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 32)

    from app.infrastructure.config import Settings

    s = Settings(_env_file=None)
    assert s.speech_agent == "stub"          # dev par défaut, sans GPU
    assert s.extractor_backend == "null"     # pas d'extraction par défaut
    assert s.default_language == "fr"
    assert s.cors_origins == []              # CORS désactivé par défaut (sûr)
    assert s.rate_limit_per_minute == 120
