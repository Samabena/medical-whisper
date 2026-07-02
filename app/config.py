"""Configuration centralisée via pydantic-settings (lecture depuis .env)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore" : le .env est partagé avec la v2 (champs supplémentaires tolérés).
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ollama_api_key: str
    ollama_model: str = "gpt-oss:120b-cloud"
    ollama_base_url: str = "https://ollama.com"

    # STT distant (serveur Whisper de l'équipe, API OpenAI-compatible).
    whisper_api_url: str = "http://srv-team-ia:9300/v1/audio/transcriptions"
    whisper_api_timeout: int = 120

    piper_voice_path: str

    session_ttl_minutes: int = 30

    api_keys: list[str] = []

    cors_origins: list[str] = []

    database_url: str = "sqlite:///./voice-to-form.db"
    admin_password: str
    admin_secret_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
