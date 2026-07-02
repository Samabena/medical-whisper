"""Tests de la configuration centralisée (INFRA-2)."""

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_valeurs_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les valeurs par défaut doivent être appliquées quand non surchargées."""
    monkeypatch.setenv("OLLAMA_API_KEY", "cle-de-test")
    monkeypatch.setenv("PIPER_VOICE_PATH", "/tmp/voices")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.ollama_api_key == "cle-de-test"
    assert settings.ollama_model == "gpt-oss:120b-cloud"
    assert settings.ollama_base_url == "https://ollama.com"
    assert settings.whisper_api_url == "http://srv-team-ia:9300/v1/audio/transcriptions"
    assert settings.whisper_api_timeout == 120
    assert settings.piper_voice_path == "/tmp/voices"
    assert settings.session_ttl_minutes == 30


def test_settings_surcharge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Les variables d'environnement doivent surcharger les valeurs par défaut."""
    monkeypatch.setenv("OLLAMA_API_KEY", "ma-cle")
    monkeypatch.setenv("PIPER_VOICE_PATH", "/data/voices")
    monkeypatch.setenv("WHISPER_API_URL", "http://autre-serveur:8000/v1/audio/transcriptions")
    monkeypatch.setenv("SESSION_TTL_MINUTES", "60")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.whisper_api_url == "http://autre-serveur:8000/v1/audio/transcriptions"
    assert settings.session_ttl_minutes == 60


def test_settings_cle_obligatoire_manquante(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une clé obligatoire absente doit lever une ValidationError claire."""
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.delenv("PIPER_VOICE_PATH", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]

    erreurs = exc_info.value.errors()
    champs_manquants = {e["loc"][0] for e in erreurs}
    assert "ollama_api_key" in champs_manquants
    assert "piper_voice_path" in champs_manquants
