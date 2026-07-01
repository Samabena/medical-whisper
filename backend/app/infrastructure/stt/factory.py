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

    if settings.stt_backend == "whisperlive_remote":
        from app.infrastructure.stt.whisperlive_remote import WhisperLiveRemoteStream

        return WhisperLiveRemoteStream(
            url=settings.whisperlive_remote_url,
            input_rate=settings.audio_input_rate,
            audio_format=settings.whisperlive_remote_audio_format,
        )

    from app.infrastructure.stt.stub import StubSttStream

    return StubSttStream()
