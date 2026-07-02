"""Sélection de l'adapter STT selon la configuration (dev stub / prod WhisperLive).

Point unique de choix : le reste de l'app ne manipule que `SttStreamPort`.
Bascule prod = `STT_BACKEND=whisperlive`.
"""

from __future__ import annotations

from app.application.ports.stt import SttStreamPort
from app.infrastructure.config import Settings


def build_stt_stream(settings: Settings) -> SttStreamPort:
    if settings.stt_backend == "whisperlive":
        from app.infrastructure.stt.whisperlive import WhisperLiveStream

        return WhisperLiveStream(
            url=settings.whisperlive_url,
            model=settings.whisper_model,
            input_rate=settings.audio_input_rate,
        )

    from app.infrastructure.stt.stub import StubSttStream

    return StubSttStream()
