"""Port TTS (VOX-6.3) — synthèse vocale.

Abstraction du moteur de synthèse (Piper en prod, stub en dev). Appelé **par phrase**
(le segmenteur `application/live/segmenter.py` découpe la réponse de l'agent) afin de
réduire le délai au premier son (cf. ARCHITECTURE §5, LIVE-7.4).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TtsPort(Protocol):
    async def synthetiser(self, texte: str, voix: str) -> bytes:
        """Synthétise `texte` avec la `voix` donnée → octets WAV (RIFF/WAVE)."""
        ...
