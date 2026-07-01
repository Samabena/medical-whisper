"""MODEL-6.3 — codec du protocole modèle (fonctions pures)."""

from __future__ import annotations

import json

from app.application.ports.speech_agent import (
    AgentTurnEnd,
    AudioChunk,
    SpeechError,
    Transcript,
)
from app.domain.value_objects import Language
from app.infrastructure.speech.protocol import decode_message, encode_init


def test_encode_init():
    msg = json.loads(encode_init("persona médicale", "voix-fr", Language.FR))
    assert msg == {"type": "init", "persona": "persona médicale", "voice": "voix-fr", "language": "fr"}


def test_decode_audio_binaire():
    ev = decode_message(b"\x00\x01\x02")
    assert isinstance(ev, AudioChunk) and ev.data == b"\x00\x01\x02"


def test_decode_texte():
    raw = json.dumps({"type": "text", "speaker": "user", "text": "bonjour", "final": True})
    ev = decode_message(raw)
    assert isinstance(ev, Transcript)
    assert ev.speaker == "user" and ev.text == "bonjour" and ev.is_final is True


def test_decode_turn_end_et_erreur():
    assert isinstance(decode_message(json.dumps({"type": "turn_end"})), AgentTurnEnd)
    err = decode_message(json.dumps({"type": "error", "message": "oups"}))
    assert isinstance(err, SpeechError) and err.message == "oups"


def test_decode_inconnu_ignore_et_illisible():
    assert decode_message(json.dumps({"type": "???"})) is None
    assert isinstance(decode_message("pas du json"), SpeechError)
