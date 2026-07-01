"""Adapter STT WhisperLive distant — serveur de l'équipe (srv-team-ia).

Le serveur expose un endpoint WebSocket `…/v1/audio/live` dont le **format de réponse
ressemble à WhisperLive** (segments JSON `text`/`completed`/`words`). On réutilise donc
toute la logique de lecture/mapping de `WhisperLiveSession`. Deux différences avec le
WhisperLive collabora standard :

1. **Configuration par query string** (`?language=fr&sample_rate=16000`) au lieu du
   handshake JSON : ce serveur ne veut PAS de trame de config (et crashe sur les trames
   texte inattendues) — on ne fait donc qu'ouvrir la WS avec les bons paramètres d'URL.
2. **Audio en PCM s16le brut** (le param `sample_rate` indique au serveur comment
   interpréter les octets), au lieu du float32 de WhisperLive. Cf. `audio_format`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlencode

from app.domain.value_objects import Language
from app.infrastructure.stt.whisperlive import WHISPER_RATE, WhisperLiveSession

logger = logging.getLogger(__name__)


@dataclass
class WhisperLiveRemoteStream:
    """Fabrique de sessions vers le endpoint WS live custom (une WS par session)."""

    url: str  # ex. ws://srv-team-ia:9300/v1/audio/live
    input_rate: int = WHISPER_RATE  # taux de l'audio entrant (micro) ⇒ rééchantillonné 16 k
    audio_format: str = "pcm_s16le"  # "pcm_s16le" (défaut, ce serveur) ou "float32"

    async def open(self, *, language: Language, hotwords: list[str]) -> WhisperLiveSession:
        import websockets

        # On annonce 16 kHz : la session rééchantillonne l'audio entrant vers WHISPER_RATE.
        # hotwords ignorés : l'endpoint custom ne les expose pas (config = query string).
        query = urlencode({"language": language.value, "sample_rate": WHISPER_RATE})
        sep = "&" if "?" in self.url else "?"
        full = f"{self.url}{sep}{query}"
        logger.info("[DIAG-STT] connexion distante: %s (audio_format=%s)", full, self.audio_format)  # DIAG TEMP
        # ping_interval=None : ce serveur ne répond pas aux pings WS de keepalive → sans ça,
        # websockets coupe la connexion au bout de ~40 s (CLOSE 1011). Le VAD/silence fait foi.
        ws = await websockets.connect(full, max_size=None, ping_interval=None)
        logger.info("[DIAG-STT] connexion distante établie")  # DIAG TEMP
        return WhisperLiveSession(
            ws=ws, input_rate=self.input_rate, audio_format=self.audio_format
        )
