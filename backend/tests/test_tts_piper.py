"""VOX-6.3 — adapter Piper : garde-fou config + integration (binaire/voix réels)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.infrastructure.tts import piper as piper_mod
from app.infrastructure.tts.piper import PiperTts


async def test_voix_absente_leve_erreur():
    with pytest.raises(ValueError):
        await PiperTts(voice_path="").synthetiser("bonjour", "")


def test_synthese_independante_de_la_boucle(monkeypatch):
    """Régression : synthèse OK même sous SelectorEventLoop (uvicorn --reload, Windows).

    L'ancienne implémentation (`asyncio.create_subprocess_exec`) y levait
    `NotImplementedError` → audio agent muet. La nouvelle déporte Piper dans un thread.
    On simule le binaire (pas de Piper réel) et on force la boucle Selector.
    """

    def fake_run(cmd, input, stdout, stderr, env=None):  # noqa: A002 — signature subprocess.run
        # Régression encodage : Piper doit être lancé avec PYTHONUTF8=1 pour que les
        # accents arrivent intacts à espeak (sinon « fièvre » → « fiever »).
        assert env is not None and env.get("PYTHONUTF8") == "1"
        Path(cmd[4]).write_bytes(b"RIFF\x00\x00\x00\x00WAVE")  # cmd = [bin, -m, modele, -f, out]
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(piper_mod.subprocess, "run", fake_run)

    loop = asyncio.SelectorEventLoop()
    try:
        wav = loop.run_until_complete(
            PiperTts(voice_path="voix.onnx", binary="piper").synthetiser("bonjour", "")
        )
    finally:
        loop.close()
    assert wav[:4] == b"RIFF"


def test_code_retour_non_nul_leve(monkeypatch):
    def fake_run(cmd, input, stdout, stderr, env=None):  # noqa: A002
        return SimpleNamespace(returncode=1, stderr=b"voix introuvable")

    monkeypatch.setattr(piper_mod.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Piper a échoué"):
        asyncio.run(PiperTts(voice_path="v.onnx").synthetiser("bonjour", ""))


@pytest.mark.integration
async def test_synthese_reelle_wav():
    """Synthèse via Piper réel (skippé sans binaire/voix)."""
    import os

    voix = os.environ.get("PIPER_VOICE_PATH")
    if not voix:
        pytest.skip("PIPER_VOICE_PATH non défini")
    wav = await PiperTts(voice_path=voix).synthetiser("Bonjour, je vous écoute.", "")
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
