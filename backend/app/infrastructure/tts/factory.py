"""Sélection de l'adapter TTS selon la configuration (dev stub / prod Piper).

Point unique de choix : le reste de l'app ne manipule que `TtsPort`.
Bascule prod :
  - `TTS_BACKEND=piper_http` (+ `PIPER_URL`) : Piper dans un conteneur dédié (recommandé, Docker).
  - `TTS_BACKEND=piper`      (+ `TTS_VOICE_PATH`) : binaire Piper local (bare-metal).
"""

from __future__ import annotations

from app.application.ports.tts import TtsPort
from app.infrastructure.config import Settings


def build_tts(settings: Settings) -> TtsPort:
    if settings.tts_backend == "piper_http":
        from app.infrastructure.tts.piper_http import PiperHttpTts

        return PiperHttpTts(url=settings.piper_url, voice=settings.tts_voice_path)

    if settings.tts_backend == "piper":
        from app.infrastructure.tts.piper import PiperTts

        return PiperTts(voice_path=settings.tts_voice_path, binary=settings.piper_binary)

    from app.infrastructure.tts.stub import StubTts

    return StubTts()
