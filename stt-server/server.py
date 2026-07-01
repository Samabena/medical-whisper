"""Serveur STT compatible WhisperLive (sous-ensemble), CPU, basé sur faster-whisper.

But : fournir un vrai backend de reconnaissance vocale **sans GPU** pour l'agent
« sandwich » (STT → agent → TTS). Parle le protocole attendu par l'adapter
`app/infrastructure/stt/whisperlive.py` (collabora/WhisperLive) :

  1. à la connexion, le client envoie une config JSON {uid, language, model, ...} ;
  2. on répond {"uid", "message": "SERVER_READY"} ;
  3. le client streame de l'audio **float32 little-endian 16 kHz** (frames binaires) ;
  4. on bufferise, on détecte la fin de parole (VAD par énergie/silence) et on émet
     {"segments": [{"text", "completed", "probability", "words":[{word,probability}]}]}.
     - segment `completed:false` = partiel (toutes ~1,5 s de parole) ;
     - segment `completed:true`  = final (après ~700 ms de silence).

Lancer :  stt-server/.venv/Scripts/python.exe server.py  [--host 0.0.0.0 --port 9090 --model small]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import sys

import numpy as np
import websockets
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stt-server")

if hasattr(sys.stdout, "reconfigure"):
    # line_buffering : flush à chaque ligne même quand stdout est redirigé vers un
    # fichier (sinon les logs restent bloqués en buffer et semblent « gelés »).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

SAMPLE_RATE = 16000
VOICE_RMS = 0.012          # seuil d'énergie : au-dessus = parole
SILENCE_MS = 1500          # silence continu ⇒ fin de parole (tolère les pauses)
MIN_SPEECH_MS = 400        # durée mini de parole pour valider un tour
MIN_FINALIZE_RMS = 0.03    # en-dessous = bout quasi-silencieux : on ne transcrit pas
PARTIAL_EVERY_MS = 1500    # cadence d'émission des partiels pendant la parole
MAX_UTTERANCE_S = 30       # garde-fou : transcrit de force au-delà
# Partiels coûteux en CPU (re-transcription du buffer) et inutiles si le déclenchement
# spéculatif est désactivé côté orchestrateur. On ne garde que le FINAL (rapide, fiable).
EMIT_PARTIALS = False

_model: WhisperModel | None = None


_PROMPTS = {
    "fr": (
        "Dictée médicale en français. Le médecin indique le nom du patient, son âge, "
        "le motif de consultation (par exemple fièvre, migraine, douleurs thoraciques) "
        "et le niveau d'urgence (faible, moyen, élevé)."
    ),
    "en": (
        "Medical dictation in English. The doctor states the patient name, age, "
        "reason for the visit (e.g. fever, migraine, chest pain) and the urgency level."
    ),
}


# Hallucinations typiques de Whisper sur du silence/bruit (jamais en dictée médicale).
_HALLUCINATIONS = (
    "amara.org",
    "sous-titres réalisés",
    "merci d'avoir regardé",
    "abonnez-vous",
    "sous-titrage",
    "♪",
)


def _normalize(audio: np.ndarray) -> np.ndarray:
    """Amplifie l'audio faible (micro peu sensible) vers un niveau exploitable par Whisper."""
    if audio.size == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if 0 < peak < 0.5:  # on ne touche pas à un signal déjà fort (évite l'écrêtage)
        audio = audio * (0.95 / peak)
    return audio


def _transcribe(audio: np.ndarray, language: str) -> tuple[str, list[dict], float]:
    """Transcription bloquante (exécutée dans un thread)."""
    assert _model is not None
    audio = _normalize(audio)
    segments, _info = _model.transcribe(
        audio,
        language=language or None,
        task="transcribe",
        beam_size=1,                       # rapide (CPU) : évite le retard / blocage
        word_timestamps=True,
        # PAS de vad_filter : trop agressif sur une voix basse (RMS ~0.03) → il jetait
        # toute la parole. On fait déjà notre propre endpointing + trim du silence.
        vad_filter=False,
        initial_prompt=_PROMPTS.get(language, _PROMPTS["fr"]),  # amorce domaine + langue
        condition_on_previous_text=False,
    )
    textes: list[str] = []
    mots: list[dict] = []
    logprobs: list[float] = []
    for seg in segments:
        textes.append(seg.text)
        logprobs.append(seg.avg_logprob)
        for w in seg.words or []:
            mots.append({"word": w.word, "probability": float(w.probability)})
    texte = "".join(textes).strip()
    # Filtre anti-hallucination : sur du silence/bruit, Whisper recrache des phrases de
    # sous-titres. On les jette (jamais présentes dans une dictée médicale réelle).
    if any(h in texte.lower() for h in _HALLUCINATIONS):
        log.info("Hallucination ignorée : %r", texte)
        return "", [], 0.0
    prob = float(math.exp(sum(logprobs) / len(logprobs))) if logprobs else 0.9
    return texte, mots, max(0.0, min(1.0, prob))


class Connection:
    def __init__(self, ws: websockets.WebSocketServerProtocol) -> None:
        self.ws = ws
        self.language = ""
        self.buffer = np.empty(0, dtype=np.float32)
        self.had_speech = False
        self.speech_samples = 0
        self.silent_samples = 0
        # File d'attente + worker UNIQUE : transcriptions sérialisées (jamais en parallèle
        # → pas de saturation CPU) sans bloquer la boucle de réception audio.
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
        self._worker = asyncio.create_task(self._transcribe_worker())

    async def run(self) -> None:
        # 1) Config JSON initiale.
        raw = await self.ws.recv()
        try:
            cfg = json.loads(raw)
        except (ValueError, TypeError):
            cfg = {}
        self.language = cfg.get("language") or ""
        uid = cfg.get("uid", "")
        log.info("Session %s langue=%r modèle=%s", uid[:8], self.language, cfg.get("model"))
        await self.ws.send(json.dumps({"uid": uid, "message": "SERVER_READY"}))

        # 2) Boucle audio.
        try:
            async for msg in self.ws:
                if isinstance(msg, (bytes, bytearray)):
                    await self._on_audio(np.frombuffer(bytes(msg), dtype="<f4"))
                elif isinstance(msg, str) and msg.strip().strip('"') == "END_OF_AUDIO":
                    # Fin de tour explicite côté client : on finalise le buffer courant
                    # quoi qu'en dise le VAD (robuste au bruit de fond du micro).
                    log.info("END_OF_AUDIO reçu → finalisation forcée")
                    self._finalize(force=True)
        finally:
            self._worker.cancel()

    async def _on_audio(self, chunk: np.ndarray) -> None:
        if chunk.size == 0:
            return
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        voiced = rms >= VOICE_RMS
        # On jette le silence/bruit AVANT le début de parole (et l'écho du « Bonjour »
        # de l'agent) pour ne transcrire que la parole utile → bien plus précis.
        if not self.had_speech and not voiced:
            return
        self.buffer = np.concatenate([self.buffer, chunk])
        if voiced:
            self.had_speech = True
            self.speech_samples += chunk.size
            self.silent_samples = 0
        else:
            self.silent_samples += chunk.size

        silence_needed = SILENCE_MS * SAMPLE_RATE // 1000
        min_speech = MIN_SPEECH_MS * SAMPLE_RATE // 1000

        # Fin de parole détectée (silence) → final.
        if self.had_speech and self.silent_samples >= silence_needed and self.speech_samples >= min_speech:
            self._finalize()
        # Garde-fou longueur.
        elif self.buffer.size >= MAX_UTTERANCE_S * SAMPLE_RATE and self.had_speech:
            self._finalize()

    def _finalize(self, *, force: bool = False) -> None:
        """Met le buffer dans la FILE de transcription et le vide aussitôt.

        La réception ne bloque jamais ; un worker unique transcrit séquentiellement."""
        if not force and not self.had_speech:
            return
        if self.buffer.size == 0:
            return
        audio = self.buffer
        rms = float(np.sqrt(np.mean(np.square(audio))))
        # On jette les bouts quasi-silencieux (silence/bruit entre les mots) : inutile à
        # transcrire et source d'hallucinations.
        if rms < MIN_FINALIZE_RMS and not force:
            self._reset_buffer()
            return
        log.info("Buffer %.1fs, RMS=%.4f → file de transcription", audio.size / SAMPLE_RATE, rms)
        self._reset_buffer()
        self._queue.put_nowait(audio)

    def _reset_buffer(self) -> None:
        self.buffer = np.empty(0, dtype=np.float32)
        self.had_speech = False
        self.speech_samples = 0
        self.silent_samples = 0

    async def _transcribe_worker(self) -> None:
        """Worker unique. À chaque cycle il FUSIONNE tous les bouts en attente et les
        transcrit en une seule passe → il rattrape toujours le retard, peu importe le
        nombre de fragments (sinon la file s'accumule plus vite qu'elle ne se vide)."""
        while True:
            chunks = [await self._queue.get()]
            while not self._queue.empty():  # draine tout ce qui s'est accumulé
                chunks.append(self._queue.get_nowait())
            audio = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
            try:
                texte, mots, prob = await asyncio.to_thread(_transcribe, audio, self.language)
                if texte:
                    seg = {"text": texte, "completed": True, "probability": prob, "words": mots}
                    await self.ws.send(json.dumps({"segments": [seg]}))
                    log.info("FINAL (%d bout(s), %.1fs) %r (p=%.2f)",
                             len(chunks), audio.size / SAMPLE_RATE, texte, prob)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — connexion fermée / transcription KO
                log.debug("Transcription/envoi KO : %s", exc)
            finally:
                for _ in chunks:
                    self._queue.task_done()


async def _handler(ws: websockets.WebSocketServerProtocol) -> None:
    try:
        await Connection(ws).run()
    except websockets.ConnectionClosed:
        pass
    except Exception:  # noqa: BLE001
        log.exception("Erreur session STT")


async def main() -> None:
    global _model
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9090)
    ap.add_argument("--model", default="small")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--cpu-threads", type=int, default=8)  # plus de threads = transcription + rapide
    args = ap.parse_args()

    log.info(
        "Chargement du modèle faster-whisper '%s' (CPU, %s, %d threads)…",
        args.model, args.compute_type, args.cpu_threads,
    )
    _model = WhisperModel(
        args.model, device="cpu", compute_type=args.compute_type, cpu_threads=args.cpu_threads
    )
    log.info("Modèle prêt. Serveur STT sur ws://%s:%d", args.host, args.port)

    async with websockets.serve(_handler, args.host, args.port, max_size=None):
        await asyncio.Future()  # tourne indéfiniment


if __name__ == "__main__":
    asyncio.run(main())
