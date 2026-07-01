"""Serveur TTS Piper — HTTP, CPU (aucun GPU).

But : isoler la synthèse vocale Piper dans un composant réseau dédié afin que le backend
n'ait plus besoin du binaire Piper ni des voix .onnx (il appelle ce serveur via HTTP —
cf. `app/infrastructure/tts/piper_http.py`).

Contrat :
  GET  /health                → 200 "ok"
  POST /synthesize            → body JSON {"text": "...", "voice": "<chemin .onnx optionnel>"}
                                200 Content-Type: audio/wav  (octets RIFF/WAVE)
                                400 si `text` manquant, 500 si Piper échoue.

Le texte est envoyé sur stdin de Piper ; le WAV est produit dans un fichier temporaire
éphémère (jamais conservé : aucune donnée de santé persistée) puis renvoyé en mémoire.

Lancer :  python server.py  [--host 0.0.0.0 --port 5000]
Config env : PIPER_VOICE (voix .onnx par défaut), PIPER_BINARY (défaut « piper »).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("piper-server")

DEFAULT_VOICE = os.environ.get("PIPER_VOICE", "")
PIPER_BINARY = os.environ.get("PIPER_BINARY", "piper")

# ⚠️ Piper (point d'entrée Python) décode stdin avec l'encodage locale : on force UTF-8
# pour que les accents (« fièvre ») arrivent intacts à espeak (sinon prononciation fausse).
_PIPER_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def synthesize(text: str, voice: str) -> bytes:
    """Appel Piper bloquant → octets WAV. Lève RuntimeError si échec."""
    modele = voice or DEFAULT_VOICE
    if not modele:
        raise ValueError("Aucune voix Piper configurée (PIPER_VOICE ou champ 'voice').")
    with tempfile.TemporaryDirectory() as tmp:
        sortie = Path(tmp) / "out.wav"
        proc = subprocess.run(
            [PIPER_BINARY, "-m", modele, "-f", str(sortie)],
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=_PIPER_ENV,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode(errors="replace")[:200]
            raise RuntimeError(f"Piper a échoué : {err}")
        return sortie.read_bytes()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # journalisation via logging
        log.info("%s - %s", self.address_string(), fmt % args)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send(200, b"ok", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/synthesize":
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
        try:
            wav = synthesize(text, voice)
        except ValueError as exc:
            self._send(400, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        except Exception as exc:  # noqa: BLE001 — remonte l'erreur Piper au client
            log.exception("Synthèse KO")
            self._send(500, json.dumps({"error": str(exc)}).encode(), "application/json")
            return
        self._send(200, wav, "audio/wav")

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
    log.info("Serveur Piper sur http://%s:%d (voix par défaut : %r)", args.host, args.port, DEFAULT_VOICE)
    # ThreadingHTTPServer : chaque requête dans son thread → synthèses concurrentes.
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
