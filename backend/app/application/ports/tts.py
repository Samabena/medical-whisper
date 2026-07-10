"""Port TTS (VOX-6.3) — synthèse vocale.

Abstraction du moteur de synthèse (Piper en prod, stub en dev). Appelé **par phrase**
(le segmenteur `application/live/segmenter.py` découpe la réponse de l'agent) afin de
réduire le délai au premier son (cf. ARCHITECTURE §5, LIVE-7.4).

Deux modes :
- `synthetiser` : renvoie un **WAV complet** (RIFF/WAVE) — simple, utilisé pour les tests
  et les appels ponctuels ;
- `stream`      : émet le **PCM brut au fil de l'eau** (chunks) — mode « live » utilisé par
  l'agent sandwich. Le premier son part avant la fin de la synthèse et la lecture est
  gapless côté navigateur.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

# Contrat de streaming : PCM signé 16 bits little-endian, mono, à ce taux (natif de la voix
# Piper fr_FR-siwis-medium). Le navigateur lit les chunks bruts à ce taux (pas d'en-tête WAV).
TTS_SAMPLE_RATE = 22050


@runtime_checkable
class TtsPort(Protocol):
    async def synthetiser(self, texte: str, voix: str) -> bytes:
        """Synthétise `texte` avec la `voix` donnée → octets WAV (RIFF/WAVE)."""
        ...

    def stream(self, texte: str, voix: str) -> AsyncIterator[bytes]:
        """Synthétise `texte` en **streaming** → chunks PCM s16le mono @ `TTS_SAMPLE_RATE`.

        Renvoie un async-itérateur : chaque chunk est émis dès qu'il est disponible. Chaque
        chunk fait un nombre **pair** d'octets (échantillons 16 bits entiers)."""
        ...
