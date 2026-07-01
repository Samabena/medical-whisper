"""Adapter STT WhisperLive (VOX-6.1) — client WebSocket vers le serveur faster-whisper.

Implémente `SttStreamPort` en parlant le protocole WhisperLive (collabora/WhisperLive) :
1. à l'ouverture, on envoie une config JSON (uid, langue, modèle, VAD, hotwords) ;
2. on streame l'audio en **float32 16 kHz** (conversion depuis PCM s16le) ;
3. le serveur renvoie des `segments` (texte + `completed`) → mappés en
   `SttPartial(stable)` / `SttFinal(words[conf])`, plus un `SttEndpoint` à la fin de parole.

Réseau réel ⇒ testé en `integration` (skippé sans serveur). En dev, on utilise le stub.
"""

from __future__ import annotations

import array
import asyncio
import json
import logging
import sys
import uuid
from dataclasses import dataclass, field

try:  # audioop : rééchantillonnage de qualité (stdlib, présent en 3.11).
    import audioop  # type: ignore
except ImportError:  # pragma: no cover — retiré en 3.13
    audioop = None  # type: ignore

WHISPER_RATE = 16000  # WhisperLive/faster-whisper attend du 16 kHz mono.

from app.application.ports.stt import (
    SttEndpoint,
    SttEvent,
    SttFinal,
    SttPartial,
    WordConf,
)
from app.domain.value_objects import Language

logger = logging.getLogger(__name__)

# Confiance mini d'un partiel pour être jugé « stable » (déclenchement spéculatif).
_STABLE_MIN_CONF = 0.6


def _pcm16_to_float32_bytes(frame: bytes) -> bytes:
    """Convertit du PCM s16le mono en float32 LE [-1, 1] (format attendu par WhisperLive).

    Stdlib uniquement (`array`) — pas de dépendance numpy côté backend.
    """
    ints = array.array("h")  # signed short (16 bits)
    ints.frombytes(frame)
    if sys.byteorder == "big":  # l'entrée est little-endian ; corriger sur plateforme BE
        ints.byteswap()
    floats = array.array("f", (s / 32768.0 for s in ints))
    if sys.byteorder == "big":  # la sortie doit rester little-endian
        floats.byteswap()
    return floats.tobytes()


@dataclass
class WhisperLiveSession:
    """Session WhisperLive : pousse l'audio, lit les segments, émet des `SttEvent`."""

    ws: object  # websockets.WebSocketClientProtocol
    input_rate: int = WHISPER_RATE
    # Encodage envoyé au serveur : "float32" (WhisperLive collabora standard) ou
    # "pcm_s16le" (serveur custom qui prend du PCM brut + sample_rate en query).
    audio_format: str = "float32"
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    def __post_init__(self) -> None:
        self._closed = False
        self._last_partial = ""
        self._rate_state = None  # état du rééchantillonneur (audioop.ratecv)
        self._reader = asyncio.create_task(self._lire())

    def _to_16k_s16le(self, frame: bytes) -> bytes:
        """Rééchantillonne le PCM s16le mono entrant vers 16 kHz (no-op si déjà à 16 k)."""
        if self.input_rate == WHISPER_RATE or not frame:
            return frame
        if audioop is None:  # repli : décimation linéaire entière simple
            ratio = self.input_rate // WHISPER_RATE
            if ratio <= 1:
                return frame
            ints = array.array("h")
            ints.frombytes(frame)
            return array.array("h", ints[::ratio]).tobytes()
        converted, self._rate_state = audioop.ratecv(
            frame, 2, 1, self.input_rate, WHISPER_RATE, self._rate_state
        )
        return converted

    async def _lire(self) -> None:
        logger.info("[DIAG-STT] reader démarré (audio_format=%s)", self.audio_format)  # DIAG TEMP
        try:
            async for raw in self.ws:  # type: ignore[attr-defined]
                if isinstance(raw, bytes):
                    logger.info("[DIAG-STT] reçu binaire %d octets", len(raw))  # DIAG TEMP
                    continue
                logger.info("[DIAG-STT] reçu texte: %s", str(raw)[:400])  # DIAG TEMP
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                if msg.get("message") in {"SERVER_READY", "WAIT"}:
                    continue
                for seg in msg.get("segments", []):
                    await self._emettre_segment(seg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[DIAG-STT] lecture interrompue : %r", exc)  # DIAG TEMP (était debug)
        finally:
            logger.info("[DIAG-STT] reader terminé")  # DIAG TEMP
            await self._queue.put(None)

    async def _emettre_segment(self, seg: dict) -> None:
        texte = (seg.get("text") or "").strip()
        if not texte:
            return
        if seg.get("completed"):
            mots = [
                WordConf(w.get("word", ""), float(w.get("probability", 1.0)))
                for w in seg.get("words", [])
            ]
            await self._queue.put(SttFinal(texte, mots))
        elif texte != self._last_partial:
            self._last_partial = texte
            conf = float(seg.get("probability", 1.0))
            await self._queue.put(SttPartial(texte, stable=conf >= _STABLE_MIN_CONF))

    async def send_audio(self, frame: bytes) -> None:
        if self._closed:
            return
        frame = self._to_16k_s16le(frame)
        if self.audio_format == "float32":
            frame = _pcm16_to_float32_bytes(frame)  # WhisperLive standard
        self._sent = getattr(self, "_sent", 0) + 1  # DIAG TEMP
        if self._sent % 50 == 1:  # DIAG TEMP : 1re, 51e, 101e… trame
            logger.info("[DIAG-STT] envoyé %d trames (dernière=%d octets, fmt=%s)", self._sent, len(frame), self.audio_format)
        await self.ws.send(frame)  # type: ignore[attr-defined]  # sinon PCM s16le brut

    async def end_turn(self) -> None:
        # Fin de parole explicite (bouton « Fin de tour ») : on demande au serveur de
        # finaliser MAINTENANT (utile si le bruit de fond du micro empêche le VAD de
        # détecter le silence), puis on signale l'endpoint local.
        if not self._closed:
            try:
                await self.ws.send("END_OF_AUDIO")  # type: ignore[attr-defined]
            except Exception as exc:  # noqa: BLE001
                logger.debug("Envoi END_OF_AUDIO impossible : %s", exc)
        await self._queue.put(SttEndpoint())

    async def events(self):
        while True:
            ev: SttEvent | None = await self._queue.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        self._closed = True
        if not self._reader.done():
            self._reader.cancel()
        try:
            await self.ws.close()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.debug("Fermeture WhisperLive : %s", exc)


@dataclass
class WhisperLiveStream:
    """Fabrique de sessions WhisperLive (réutilise l'URL/modèle ; une WS par session)."""

    url: str
    model: str = "large-v3"
    input_rate: int = WHISPER_RATE  # taux de l'audio entrant (rééchantillonné → 16 k)

    async def open(self, *, language: Language, hotwords: list[str]) -> WhisperLiveSession:
        import websockets

        ws = await websockets.connect(self.url, max_size=None)
        config = {
            "uid": str(uuid.uuid4()),
            "language": language.value,
            "task": "transcribe",
            "model": self.model,
            "use_vad": True,
            "send_last_n_segments": 1,
        }
        if hotwords:
            config["hotwords"] = " ".join(hotwords)
        await ws.send(json.dumps(config))
        return WhisperLiveSession(ws=ws, input_rate=self.input_rate)
