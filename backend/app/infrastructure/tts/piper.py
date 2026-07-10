"""Adapter TTS Piper (VOX-6.3) — synthèse locale, voix FR.

Implémente `TtsPort` en appelant l'exécutable Piper : le texte est envoyé sur stdin,
Piper écrit un WAV PCM au taux propre à la voix (ex. 22050 Hz pour fr_FR-siwis-medium ;
l'en-tête WAV porte le taux réel, le navigateur le décode correctement). On lit les octets
en mémoire (aucune donnée de santé persistée sur disque). Appelé **par phrase** par le
pipeline (segmenteur), ce qui réduit le délai au premier son.

Dépend d'un binaire/voix réels ⇒ testé en `integration` (skippé en CI). En dev, on
utilise le stub.

⚠️ **Windows + `uvicorn --reload`** : la boucle d'événements est alors le `SelectorEventLoop`,
qui ne supporte PAS `asyncio.create_subprocess_exec` (lève `NotImplementedError` → audio agent
muet). On lance donc Piper via un `subprocess.run` **bloquant déporté dans un thread**
(`asyncio.to_thread`) : indépendant de la politique de boucle, fonctionne sous Selector comme
Proactor, sans bloquer l'event loop.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# ⚠️ Encodage stdin de Piper. Le binaire `piper` est un point d'entrée Python : sous
# Windows, il décode stdin avec l'encodage locale (cp1252), PAS UTF-8. Les octets UTF-8
# des lettres accentuées (« è » = 0xC3 0xA8) sont alors mal interprétés → espeak phonémise
# du charabia et la voix prononce de travers (« fiever » au lieu de « fièvre »). On force
# donc l'interpréteur de Piper en UTF-8 pour que les accents arrivent intacts.
_PIPER_ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


@dataclass
class PiperTts:
    """Synthèse Piper via l'exécutable (`piper -m voix.onnx -f sortie.wav`)."""

    voice_path: str
    binary: str = "piper"

    def _synthetiser_bloquant(self, texte: str, modele: str) -> bytes:
        """Appel Piper synchrone (exécuté dans un thread). WAV lu en mémoire."""
        # Fichier temporaire éphémère, supprimé immédiatement après lecture.
        with tempfile.TemporaryDirectory() as tmp:
            sortie = Path(tmp) / "out.wav"
            proc = subprocess.run(
                [self.binary, "-m", modele, "-f", str(sortie)],
                input=texte.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                env=_PIPER_ENV,  # PYTHONUTF8=1 : accents transmis intacts à espeak
            )
            if proc.returncode != 0:
                err = (proc.stderr or b"").decode(errors="replace")[:200]
                raise RuntimeError(f"Piper a échoué : {err}")
            return sortie.read_bytes()

    async def synthetiser(self, texte: str, voix: str) -> bytes:
        modele = voix or self.voice_path
        if not modele:
            raise ValueError("Aucune voix Piper configurée (tts_voice_path).")
        # Déport dans un thread : évite le NotImplementedError des subprocess asyncio
        # sous SelectorEventLoop (uvicorn --reload, Windows) sans bloquer la boucle.
        return await asyncio.to_thread(self._synthetiser_bloquant, texte, modele)

    async def stream(self, texte: str, voix: str) -> AsyncIterator[bytes]:
        """Mode « live » : synthétise le WAV puis en émet le PCM en chunks.

        Le binaire Piper ne streame pas nativement : on récupère le WAV complet puis on
        extrait le PCM (sans l'en-tête RIFF) découpé en morceaux. La voix fr_FR-siwis-medium
        est à TTS_SAMPLE_RATE, cohérent avec le contrat de streaming."""
        wav = await self.synthetiser(texte, voix)
        with wave.open(io.BytesIO(wav), "rb") as w:
            pcm = w.readframes(w.getnframes())
        step = 8192
        for i in range(0, len(pcm), step):
            yield pcm[i : i + step]
