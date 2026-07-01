"""LIVE-7.4 — événements de latence du port (endpoint spéculatif, backchannel, partiel stable)."""

from __future__ import annotations

from typing import get_args

from app.application.ports.speech_agent import (
    Backchannel,
    SpeechEndpoint,
    SpeechEvent,
    Transcript,
)


def test_transcript_partiel_stable_defaut_faux():
    t = Transcript("le patient s'appelle", "user")
    assert t.is_final is False and t.stable is False
    stable = Transcript("le patient s'appelle Martin", "user", stable=True)
    assert stable.stable is True


def test_endpoint_et_backchannel_dans_l_union():
    membres = get_args(SpeechEvent)
    assert SpeechEndpoint in membres
    assert Backchannel in membres


def test_backchannel_audio_optionnel():
    bc = Backchannel("D'accord…")
    assert bc.text == "D'accord…" and bc.audio is None
    with_audio = Backchannel("D'accord…", audio=b"\x00")
    assert with_audio.audio == b"\x00"
