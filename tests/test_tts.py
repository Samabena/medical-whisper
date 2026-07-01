"""Tests du service TTS (CORE-3)."""

from __future__ import annotations

import wave
from unittest.mock import MagicMock, patch

import pytest

from app.services.tts import synthetiser


# ── Tests unitaires (Piper mocké) ─────────────────────────────────────────────


def _fake_synthesize(texte: str, wav_file: wave.Wave_write) -> None:
    """Écrit un WAV silencieux valide pour simuler Piper."""
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(22050)
    wav_file.writeframes(b"\x00" * 200)


def test_synthetiser_retourne_bytes_non_vides() -> None:
    """synthetiser() doit retourner des bytes non vides."""
    mock_voice = MagicMock()
    mock_voice.synthesize_wav.side_effect = _fake_synthesize

    with patch("app.services.tts._get_voice", return_value=mock_voice):
        resultat = synthetiser("bonjour")

    assert len(resultat) > 0


def test_synthetiser_entete_riff_wave() -> None:
    """Les bytes retournés doivent avoir un en-tête RIFF/WAVE valide."""
    mock_voice = MagicMock()
    mock_voice.synthesize_wav.side_effect = _fake_synthesize

    with patch("app.services.tts._get_voice", return_value=mock_voice):
        resultat = synthetiser("bonjour")

    assert resultat[:4] == b"RIFF", "Les 4 premiers bytes doivent être 'RIFF'"
    assert resultat[8:12] == b"WAVE", "Les bytes 8-12 doivent être 'WAVE'"


def test_synthetiser_appelle_synthesize_avec_texte() -> None:
    """synthetiser() doit passer le texte exact à voice.synthesize_wav."""
    mock_voice = MagicMock()
    mock_voice.synthesize_wav.side_effect = _fake_synthesize

    with patch("app.services.tts._get_voice", return_value=mock_voice):
        synthetiser("Quelle est la date de l'intervention ?")

    args, _ = mock_voice.synthesize_wav.call_args
    assert args[0] == "Quelle est la date de l'intervention ?"


def test_synthetiser_texte_vide() -> None:
    """synthetiser() avec texte vide doit retourner un WAV valide (silence)."""
    mock_voice = MagicMock()
    mock_voice.synthesize_wav.side_effect = _fake_synthesize

    with patch("app.services.tts._get_voice", return_value=mock_voice):
        resultat = synthetiser("")

    assert resultat[:4] == b"RIFF"


# ── Test d'intégration (Piper réel) ──────────────────────────────────────────


@pytest.mark.integration
def test_synthetiser_voix_reelle() -> None:
    """synthetiser() avec la vraie voix Piper doit retourner un WAV non vide."""
    import os

    from app.config import get_settings

    voice_path = get_settings().piper_voice_path
    if not os.path.exists(voice_path):
        pytest.skip(f"Voix Piper absente ({voice_path}) — test d'intégration ignoré")

    import app.services.tts as tts_module

    tts_module._voice = None  # réinitialise le singleton

    resultat = synthetiser("Bonjour, ceci est un test de synthèse vocale.")

    assert len(resultat) > 44, "WAV trop court (header seul = 44 bytes)"
    assert resultat[:4] == b"RIFF"
    assert resultat[8:12] == b"WAVE"
