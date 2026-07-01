"""Codec du protocole WebSocket modèle (fonctions pures, testables).

Protocole JSON+binaire de notre relais :
- sortant `init`      : {"type":"init","persona":...,"voice":...,"language":...}
- sortant `end_turn`  : {"type":"end_turn"}
- entrant texte       : {"type":"text","speaker":"user|agent","text":...,"final":bool}
- entrant fin de tour : {"type":"turn_end"}
- entrant erreur      : {"type":"error","message":...}
- entrant audio       : trame BINAIRE brute → AudioChunk

⚠️ EPIC 11.1 : valider/aligner ce mapping sur le wire-format réel de Moshi/PersonaPlex.
"""

from __future__ import annotations

import json

from app.application.ports.speech_agent import (
    AgentTurnEnd,
    AudioChunk,
    SpeechError,
    SpeechEvent,
    Transcript,
)
from app.domain.value_objects import Language


def encode_init(persona: str, voice: str, language: Language) -> str:
    return json.dumps(
        {"type": "init", "persona": persona, "voice": voice, "language": language.value}
    )


def encode_end_turn() -> str:
    return json.dumps({"type": "end_turn"})


def decode_message(raw: str | bytes) -> SpeechEvent | None:
    """Transforme une trame WS en événement. Trame binaire = audio ; JSON = contrôle/texte."""
    if isinstance(raw, (bytes, bytearray)):
        return AudioChunk(bytes(raw))
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return SpeechError(f"Trame illisible : {raw!r:.80}")

    type_ = msg.get("type")
    if type_ == "text":
        return Transcript(
            text=msg.get("text", ""),
            speaker=msg.get("speaker", "agent"),
            is_final=bool(msg.get("final", False)),
        )
    if type_ == "turn_end":
        return AgentTurnEnd()
    if type_ == "error":
        return SpeechError(msg.get("message", "erreur modèle"))
    return None  # type inconnu : ignoré
