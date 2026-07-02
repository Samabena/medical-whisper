"""Configuration 12-factor (CORE-0.2).

Tous les réglages proviennent de l'environnement (`.env` en dev, secrets en prod).
Les secrets (`jwt_secret`, `admin_password`) sont **obligatoires** : leur absence
provoque une erreur explicite au démarrage plutôt qu'un défaut non sûr.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Persistance -------------------------------------------------------
    database_url: str = "postgresql+asyncpg://vtf:vtf@db:5432/voicetoform"
    redis_url: str = "redis://redis:6379/0"

    # --- Agent vocal ------------------------------------------------------
    # Architecture cible v3 = « sandwich » (STT → agent + extracteur → TTS).
    # sandwich    : v3, compose STT (stt_backend) + agent LLM + TTS (tts_backend).
    # stub        : agent vocal scripté, AUCUN GPU requis (dev).
    # llm         : agent conversationnel texte seul (Ollama), dev sans STT/TTS.
    speech_agent: Literal["stub", "llm", "sandwich"] = "stub"

    # --- STT : reconnaissance vocale streaming (v3) -----------------------
    # stub        : transcripts scriptés déterministes (dev sans GPU/réseau).
    # whisperlive : client WebSocket vers le serveur WhisperLive en ligne de l'équipe
    #               (handshake JSON + audio float32).
    stt_backend: Literal["stub", "whisperlive"] = "stub"
    whisperlive_url: str = "ws://srv-team-ia:9300"  # serveur STT en ligne de l'équipe
    whisper_model: str = "small"  # transmis dans le handshake (small dev CPU ; large-v3 GPU)
    stt_language: Literal["en", "fr", ""] = ""  # vide ⇒ langue du compte/formulaire
    # Taux d'échantillonnage de l'audio entrant (micro). Le front capture en 24 kHz ;
    # WhisperLive attend du 16 kHz ⇒ rééchantillonnage si besoin.
    audio_input_rate: int = 24000

    # --- TTS : synthèse vocale (v3) ---------------------------------------
    # stub       : WAV de silence valide (dev/test, déterministe).
    # piper      : binaire Piper local (bare-metal), voix FR (synthèse par phrase).
    # piper_http : serveur Piper distant dans un conteneur dédié (Docker, recommandé).
    tts_backend: Literal["stub", "piper", "piper_http"] = "stub"
    tts_voice_path: str = ""  # chemin du modèle de voix Piper (.onnx) — voix par défaut
    piper_binary: str = "piper"  # exécutable Piper (PATH ou chemin absolu) — backend `piper`
    piper_url: str = "http://piper:5000"  # serveur Piper HTTP — backend `piper_http`

    # --- Extraction LLM (texte) -------------------------------------------
    # null    : aucune extraction (plomberie pure).
    # keyword : extraction déterministe « champ: valeur » (dev/test, sans LLM).
    # ollama  : extraction NL réelle via Ollama (auto-hébergeable, données de santé).
    extractor_backend: Literal["null", "keyword", "ollama"] = "null"
    ollama_host: str = "https://ollama.com"  # Ollama Cloud (clé API requise)
    ollama_model: str = "gpt-oss:120b-cloud"
    ollama_api_key: str = ""
    # Modèles distincts agent (rapide) / extracteur (précis) — vide ⇒ `ollama_model`.
    llm_agent_model: str = ""
    llm_extractor_model: str = ""
    # Agent conversationnel du sandwich : scripted (dev, sans LLM) ou ollama (streaming).
    agent_backend: Literal["scripted", "ollama"] = "scripted"

    # --- Sécurité (OBLIGATOIRES, pas de défaut) ---------------------------
    jwt_secret: str
    admin_email: str = "admin@local"
    admin_password: str = ""  # mot de passe admin en clair (dev)
    admin_password_hash: str = ""  # OU hash argon2 (prod) — prioritaire s'il est fourni
    admin_access_ttl_minutes: int = 30
    admin_refresh_ttl_days: int = 7
    rate_limit_per_minute: int = 120

    # --- Latence du pipeline live (LIVE-7.4) ------------------------------
    # Leviers de réduction de latence, tous désactivables (défauts sûrs). Cf.
    # ARCHITECTURE.md §5 « Stratégies de réduction de latence ».
    # Déclenchement spéculatif : l'agent démarre sur la fin de parole détectée
    # (VAD) + le meilleur partiel stable, sans attendre le final validé (~2–3 s).
    speculative_trigger: bool = False
    vad_silence_ms: int = 700  # silence ⇒ fin de parole (endpointing)
    vad_min_chunk_ms: int = 200  # durée mini d'un segment avant émission
    partial_confidence_min: float = 0.6  # seuil de confiance d'un partiel « stable »
    # Barge-in : la reprise de parole annule l'agent + la file TTS en cours.
    barge_in: bool = True
    # Backchannel : court accusé joué immédiatement pour masquer la latence.
    backchannel: bool = False
    backchannel_text: str = "D'accord…"
    # Extraction debounced (hors chemin critique) ; 0 = immédiate.
    extractor_debounce_ms: int = 300
    # Borne de tokens de génération de l'agent. ⚠️ Les modèles à RAISONNEMENT (gpt-oss…)
    # consomment ce budget en raisonnement caché AVANT d'émettre la réponse parlée : trop bas
    # (ex. 120) → tout part dans le raisonnement → `content` vide → agent muet/garbled. On
    # prévoit donc large ; le modèle s'arrête de lui-même après sa phrase (pas de surcoût de
    # latence). La concision est obtenue par le prompt système (1–2 phrases), pas par ce plafond.
    agent_max_tokens: int = 1024
    # TTS pipeliné : synthèse par phrase/clause (1er son plus tôt).
    tts_sentence_chunking: bool = True
    # Cache du préfixe de prompt stable (système + schéma) côté LLM.
    prompt_cache: bool = True

    # --- Divers ------------------------------------------------------------
    default_language: Literal["en", "fr"] = "fr"
    cors_origins: list[str] = []
    session_token_ttl_seconds: int = 60
    # Rétention courte du formulaire final (donnée de santé) avant purge.
    result_retention_seconds: int = 600
    # Garde-fou anti-boucle : nombre max de tours de parole avant clôture « incomplet ».
    max_user_turns: int = 12

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_assez_long(cls, v: str) -> str:
        if len(v) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(f"JWT_SECRET doit faire au moins {JWT_SECRET_MIN_LENGTH} caractères.")
        return v


@lru_cache
def get_settings() -> Settings:
    """Singleton caché des réglages (instancié une seule fois)."""
    return Settings()
