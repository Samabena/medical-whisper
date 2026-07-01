"""Adapter TTS Piper **HTTP** — Piper tourne dans son propre conteneur (service `piper`).

Contrairement à `PiperTts` (qui lance le binaire Piper en sous-processus local), cet adapter
appelle un **serveur Piper distant** par HTTP. Cela permet d'isoler Piper dans un composant
Docker dédié (`piper-server/`) : le backend ne dépend plus du binaire ni de la voix .onnx.

Contrat du serveur (`piper-server/server.py`) :
  POST {url}/synthesize   body JSON {"text": "...", "voice": "<chemin .onnx optionnel>"}
                          → 200  Content-Type: audio/wav  (octets RIFF/WAVE)

Appelé **par phrase** par le pipeline (segmenteur) pour réduire le délai au premier son.
Aucune donnée de santé persistée : le WAV est lu en mémoire et jamais écrit sur disque.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
