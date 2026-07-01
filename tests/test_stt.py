"""Tests du service STT (CORE-1) — client HTTP vers le serveur Whisper distant."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from app.services.stt import STTError, transcrire


def _reponse(text: str) -> MagicMock:
    """Crée une réponse `requests` factice renvoyant {"text": ...}."""
    r = MagicMock()
    r.json.return_value = {"text": text}
    r.raise_for_status.return_value = None
    return r


@pytest.fixture(autouse=True)
def _settings_stt() -> MagicMock:
    """Mocke la config pour isoler le STT du fichier .env du projet."""
    settings = MagicMock()
    settings.whisper_api_url = "http://srv-team-ia:9300/v1/audio/transcriptions"
    settings.whisper_api_timeout = 120
    with patch("app.services.stt.get_settings", return_value=settings):
        yield settings


# ── Tests unitaires (HTTP mocké) ──────────────────────────────────────────────


def test_transcrire_retourne_texte() -> None:
    """Le champ "text" de la réponse JSON doit être renvoyé proprement (strip)."""
    with patch("app.services.stt.open", mock_open(read_data=b"audio")), patch(
        "app.services.stt.requests.post", return_value=_reponse("  Bonjour monde  ")
    ) as post:
        resultat = transcrire("/audio/test.wav")

    assert resultat == "Bonjour monde"
    # La langue française est bien transmise au serveur.
    assert post.call_args.kwargs["data"] == {"language": "fr"}


def test_transcrire_sans_parole() -> None:
    """Un audio sans parole (texte vide) doit retourner une chaîne vide."""
    with patch("app.services.stt.open", mock_open(read_data=b"audio")), patch(
        "app.services.stt.requests.post", return_value=_reponse("")
    ):
        assert transcrire("/audio/silence.wav") == ""


def test_transcrire_audio_illisible() -> None:
    """Une erreur HTTP doit lever STTError (échec remonté, pas masqué)."""
    reponse = MagicMock()
    reponse.raise_for_status.side_effect = RuntimeError("400 Bad Request")
    with patch("app.services.stt.open", mock_open(read_data=b"audio")), patch(
        "app.services.stt.requests.post", return_value=reponse
    ):
        with pytest.raises(STTError):
            transcrire("/audio/corrompu.wav")


def test_transcrire_serveur_indisponible() -> None:
    """Une erreur réseau (connexion impossible) doit aussi lever STTError."""
    with patch("app.services.stt.open", mock_open(read_data=b"audio")), patch(
        "app.services.stt.requests.post", side_effect=ConnectionError("serveur HS")
    ):
        with pytest.raises(STTError):
            transcrire("/audio/test.wav")


# ── Test d'intégration (serveur réel) ─────────────────────────────────────────


@pytest.mark.integration
def test_transcrire_fichier_reel() -> None:
    """Transcrit un vrai fichier .wav FR — nécessite le serveur Whisper joignable."""
    chemin = Path(__file__).parent / "fixtures" / "sample_fr.wav"
    if not chemin.exists():
        pytest.skip("Fichier tests/fixtures/sample_fr.wav absent")

    resultat = transcrire(str(chemin))

    assert isinstance(resultat, str)
    assert len(resultat) > 0, "La transcription d'un fichier réel ne doit pas être vide"
