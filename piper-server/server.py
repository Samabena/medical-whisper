"""Serveur TTS Piper — HTTP, CPU (aucun GPU).

But : isoler la synthèse vocale Piper dans un composant réseau dédié afin que le backend
n'ait plus besoin du binaire Piper ni des voix .onnx (il appelle ce serveur via HTTP —
cf. `app/infrastructure/tts/piper_http.py`).

Niveau 1 « live » : la voix .onnx est **chargée une seule fois en mémoire au démarrage**
(API Python `PiperVoice`), au lieu de relancer le binaire Piper — qui rechargeait le
modèle (~60 Mo) — à CHAQUE phrase. C'est le principal gain de latence sur le premier son.

Contrat :
  GET  /health                → 200 "ok" si la voix par défaut est chargée, 503 sinon
  POST /synthesize            → body JSON {"text": "...", "voice": "<chemin .onnx optionnel>"}
                                200 Content-Type: audio/wav  (octets RIFF/WAVE, complet)
                                400 si `text` manquant, 500 si la synthèse échoue.
  POST /stream                → même body ; réponse **chunked** (Transfer-Encoding: chunked)
                                Content-Type: application/octet-stream, header X-Sample-Rate.
                                Corps = PCM s16le mono émis phrase par phrase AU FIL DE L'EAU
                                (mode « live » : le premier son part sans attendre la fin).

Aucune donnée de santé persistée : l'audio est produit en mémoire, jamais écrit sur disque.

Lancer :  python server.py  [--host 0.0.0.0 --port 5000]
Config env : PIPER_VOICE (voix .onnx par défaut).
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from piper import PiperVoice

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("piper-server")

DEFAULT_VOICE = os.environ.get("PIPER_VOICE", "")

# Cache des voix chargées, clé = chemin .onnx. Rempli au démarrage (voix par défaut) et
# à la demande si une requête réclame une autre voix. onnxruntime charge le modèle une fois.
_voices: dict[str, PiperVoice] = {}
_load_lock = threading.Lock()
# La synthèse est CPU-bound : on sérialise pour éviter que N threads se battent pour le CPU
# (le parallélisme ne ferait que thrasher). Un verrou global suffit à cette échelle.
_synth_lock = threading.Lock()


def _get_voice(path: str) -> PiperVoice:
    """Retourne la voix chargée pour `path`, la chargeant (et mettant en cache) au besoin."""
    voice = _voices.get(path)
    if voice is not None:
        return voice
    with _load_lock:
        voice = _voices.get(path)  # re-check après acquisition (double-checked locking)
        if voice is None:
            log.info("Chargement de la voix Piper : %s", path)
            voice = PiperVoice.load(path)
            _voices[path] = voice
    return voice


def synthesize(text: str, voice_path: str) -> bytes:
    """Synthèse Piper **en mémoire** → octets WAV. Lève RuntimeError/ValueError si échec."""
    modele = voice_path or DEFAULT_VOICE
    if not modele:
        raise ValueError("Aucune voix Piper configurée (PIPER_VOICE ou champ 'voice').")
    voice = _get_voice(modele)
    buf = io.BytesIO()
    with _synth_lock, wave.open(buf, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)
    data = buf.getvalue()
    if not data:
        raise RuntimeError("Piper n'a produit aucun WAV.")
    return data


def _sample_rate(voice) -> int:
    """Taux d'échantillonnage de la voix (config Piper), 22050 par défaut."""
    cfg = getattr(voice, "config", None)
    return int(getattr(cfg, "sample_rate", 22050) or 22050)


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 : requis pour le Transfer-Encoding: chunked de /stream (keep-alive OK car
    # /synthesize et /health envoient un Content-Length).
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # journalisation via logging
        log.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            # 200 seulement si la voix par défaut est bien chargée : un modèle corrompu
            # fait échouer le démarrage → /health renvoie 503 (au lieu de 200 trompeur).
            if not DEFAULT_VOICE or DEFAULT_VOICE in _voices:
                self._send(200, b"ok", "text/plain")
            else:
                self._send(503, b"voice not loaded", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        route = self.path.rstrip("/")
        if route not in ("/synthesize", "/stream"):
            self._send(404, b"not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = (payload.get("text") or "").strip()
            voice = payload.get("voice") or ""
        except (ValueError, TypeError):
            self._send(400, b'{"error":"corps JSON invalide"}', "application/json")
            return
        if not text:
            self._send(400, b'{"error":"champ text requis"}', "application/json")
            return
        if route == "/stream":
            self._synthesize_stream(text, voice)
            return
        try:
            wav = synthesize(text, voice)
        except ValueError as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        except Exception as exc:  # noqa: BLE001 — remonte l'erreur au client
            log.exception("Synthèse KO")
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        self._send(200, wav, "audio/wav")

    def _synthesize_stream(self, text: str, voice_path: str) -> None:
        """Streame le PCM s16le AU FIL DE L'EAU (une passe Piper par phrase), en chunked."""
        modele = voice_path or DEFAULT_VOICE
        if not modele:
            self._send(400, b'{"error":"aucune voix configuree"}', "application/json")
            return
        try:
            voice = _get_voice(modele)
        except Exception as exc:  # noqa: BLE001 — modèle absent/corrompu : rien n'est encore envoyé
            log.exception("Chargement voix KO")
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        # En-têtes envoyés AVANT le 1er chunk : impossible de renvoyer un code d'erreur ensuite.
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("X-Sample-Rate", str(_sample_rate(voice)))
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            with _synth_lock:
                for chunk in voice.synthesize(text):  # 1 AudioChunk par phrase
                    pcm = chunk.audio_int16_bytes
                    if pcm:
                        self._write_chunk(pcm)
            self._write_chunk(b"")  # chunk terminal (0\r\n\r\n)
        except Exception:  # noqa: BLE001 — flux déjà commencé : on ne peut que couper
            log.exception("Streaming KO (flux interrompu)")
            try:
                self.wfile.write(b"0\r\n\r\n")
            except Exception:  # noqa: BLE001
                pass

    def _write_chunk(self, data: bytes) -> None:
        """Écrit un chunk HTTP (taille hex + CRLF + données + CRLF) et flush pour l'envoyer."""
        self.wfile.write(f"{len(data):X}\r\n".encode("ascii"))
        if data:
            self.wfile.write(data)
        self.wfile.write(b"\r\n")
        self.wfile.flush()

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    # Précharge la voix par défaut au démarrage : échoue vite et clairement si le .onnx
    # est corrompu/manquant (au lieu de crasher à la 1re synthèse comme avant).
    if DEFAULT_VOICE:
        try:
            _get_voice(DEFAULT_VOICE)
            log.info("Voix par défaut chargée : %s", DEFAULT_VOICE)
        except Exception:  # noqa: BLE001
            log.exception("Échec du chargement de la voix par défaut %s", DEFAULT_VOICE)
    log.info("Serveur Piper sur http://%s:%d (voix par défaut : %r)", args.host, args.port, DEFAULT_VOICE)
    # ThreadingHTTPServer : chaque requête dans son thread (la synthèse reste sérialisée).
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
