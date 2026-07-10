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


async def test_stream_emet_du_pcm_en_plusieurs_chunks():
    """Le mode live émet du PCM brut (pas de RIFF/WAVE), en chunks pairs et non vides."""
    chunks = [c async for c in StubTts().stream("une phrase à synthétiser en streaming", "v")]
    assert len(chunks) >= 2  # plusieurs chunks (flux progressif)
    assert all(len(c) % 2 == 0 and c for c in chunks)  # échantillons 16 bits entiers
    assert b"".join(chunks)[:4] != b"RIFF"  # PCM brut, pas de conteneur WAV
