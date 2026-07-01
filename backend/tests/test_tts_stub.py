"""VOX-6.3 — TTS stub : WAV RIFF/WAVE valide, taille proportionnelle au texte."""

from __future__ import annotations

from app.infrastructure.tts.stub import StubTts


async def test_wav_valide():
    wav = await StubTts().synthetiser("bonjour", "voix-fr")
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert b"data" in wav


async def test_taille_proportionnelle_au_texte():
    court = await StubTts().synthetiser("oui", "v")
    long = await StubTts().synthetiser("une phrase nettement plus longue à synthétiser", "v")
    assert len(long) > len(court)
