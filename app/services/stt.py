"""Service Speech-to-Text (Whisper distant — API OpenAI-compatible).

Au lieu de charger un modèle faster-whisper en local, on délègue la
transcription au serveur Whisper de l'équipe via une requête HTTP
`POST /v1/audio/transcriptions` (multipart : fichier audio + langue).
"""

from __future__ import annotations

import logging

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


class STTError(RuntimeError):
    """Échec de transcription : serveur indisponible ou audio illisible."""


def transcrire(chemin_audio: str) -> str:
    """Transcrit un fichier audio en texte via le serveur Whisper distant.

    Retourne '' si l'audio ne contient aucune parole (silence).
    Lève STTError si le serveur est indisponible ou l'audio illisible.
    """
    settings = get_settings()
    try:
        with open(chemin_audio, "rb") as f:
            response = requests.post(
                settings.whisper_api_url,
                files={"file": f},
                data={"language": "fr"},
                timeout=settings.whisper_api_timeout,
            )
        response.raise_for_status()
        return (response.json().get("text") or "").strip()
    except Exception as exc:
        logger.warning("Transcription échouée (%s) : %s", chemin_audio, exc)
        raise STTError(f"Transcription impossible : {exc}") from exc
