"""Adapter TTS Piper **HTTP** — Piper tourne dans son propre conteneur (service `piper`).

Contrairement à `PiperTts` (qui lance le binaire Piper en sous-processus local), cet adapter
appelle un **serveur Piper distant** par HTTP. Cela permet d'isoler Piper dans un composant
Docker dédié (`piper-server/`) : le backend ne dépend plus du binaire ni de la voix .onnx.

Contrat du serveur (`piper-server/server.py`) :
  POST {url}/synthesize   → 200 audio/wav (WAV complet)              → `synthetiser`
  POST {url}/stream       → 200 chunked, PCM s16le mono @ X-Sample-Rate → `stream` (live)

Appelé **par phrase** par le pipeline (segmenteur) pour réduire le délai au premier son.
Aucune donnée de santé persistée : l'audio est lu en mémoire et jamais écrit sur disque.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PiperHttpTts:
    """Synthèse Piper via un serveur HTTP dédié (service Docker `piper`)."""

    url: str  # ex. http://piper:5000
    voice: str = ""  # voix par défaut (le serveur en a une aussi) ; surchargée par `voix`
    timeout_s: float = 30.0

    async def synthetiser(self, texte: str, voix: str) -> bytes:
        modele = voix or self.voice  # vide ⇒ le serveur utilise sa voix par défaut
        base = self.url.rstrip("/")
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(
                f"{base}/synthesize",
                json={"text": texte, "voice": modele},
            )
        if resp.status_code != 200:
            detail = resp.text[:200]
            raise RuntimeError(f"Serveur Piper a répondu {resp.status_code} : {detail}")
        return resp.content

    async def stream(self, texte: str, voix: str) -> AsyncIterator[bytes]:
        """Streame le PCM depuis /stream, chunk par chunk (mode « live »).

        Garantit des chunks de taille **paire** (échantillons 16 bits entiers) en reportant
        un éventuel octet orphelin d'un chunk réseau sur le suivant."""
        modele = voix or self.voice
        base = self.url.rstrip("/")
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            async with client.stream(
                "POST", f"{base}/stream", json={"text": texte, "voice": modele}
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread())[:200].decode(errors="replace")
                    raise RuntimeError(f"Serveur Piper a répondu {resp.status_code} : {detail}")
                reste = b""  # octet orphelin éventuel (frontière réseau au milieu d'un échantillon)
                async for chunk in resp.aiter_bytes():
                    if not chunk:
                        continue
                    buf = reste + chunk
                    pair = len(buf) - (len(buf) % 2)
                    reste = buf[pair:]
                    if pair:
                        yield buf[:pair]
                if reste:  # ne devrait pas arriver (PCM 16 bits = pair) ; on complète par sûreté
                    yield reste + b"\x00"
