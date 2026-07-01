"""Service Text-to-Speech (Piper)."""

from __future__ import annotations

import io
import logging
import wave

from app.config import get_settings

logger = logging.getLogger(__name__)
_voice = None


def _get_voice():
    global _voice
    if _voice is None:
        from piper import PiperVoice
        settings = get_settings()
        _voice = PiperVoice.load(settings.piper_voice_path)
        logger.info("Piper chargé : %s", settings.piper_voice_path)
    return _voice


def synthetiser(texte: str) -> bytes:
    """Synthétise du texte en audio WAV (bytes)."""
    voice = _get_voice()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        # piper-tts >= 1.3 : l'écriture WAV se fait via synthesize_wav().
        # (l'ancien synthesize(texte, wav_file) interprétait wav_file comme un
        #  SynthesisConfig et laissait l'en-tête WAV non initialisé.)
        voice.synthesize_wav(texte, wav_file)
    return buf.getvalue()
