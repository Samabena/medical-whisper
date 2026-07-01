"""Configuration pytest partagée — env vars, DB in-memory, settings cache."""

import pytest

from app.config import get_settings

TEST_API_KEY = "cle-api-test-1234"
TEST_ADMIN_PASSWORD = "test-admin-pass"


@pytest.fixture(autouse=True)
def env_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Injecte les variables d'environnement minimales et vide le cache settings."""
    monkeypatch.setenv("OLLAMA_API_KEY", "cle-test")
    monkeypatch.setenv("PIPER_VOICE_PATH", "/tmp/test-voices")
    monkeypatch.setenv("API_KEYS", f'["{TEST_API_KEY}"]')
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_ADMIN_PASSWORD)
    monkeypatch.setenv("ADMIN_SECRET_KEY", "cle-secrete-test")
    get_settings.cache_clear()

    # DB admin in-memory pour chaque test
    import app.admin.database as db_mod

    db_mod.reset_engine()
    db_mod.creer_tables()

    yield

    db_mod.reset_engine()
    get_settings.cache_clear()
