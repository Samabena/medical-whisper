"""LIVE-7.4 — segmenteur de phrases pour le TTS pipeliné."""

from __future__ import annotations

from app.application.live.segmenter import aiter_sentences, iter_sentences


def test_decoupe_par_ponctuation():
    fragments = ["Bonjour", ". Quel ", "est votre nom", " ?"]
    assert list(iter_sentences(fragments)) == ["Bonjour.", "Quel est votre nom ?"]


def test_emet_la_premiere_phrase_avant_la_fin_du_flux():
    """Le gain de latence : la 1ʳᵉ phrase tombe sans attendre la suite."""
    gen = iter_sentences(iter(["Première phrase. ", "deuxième moitié"]))
    assert next(gen) == "Première phrase."  # émise immédiatement


def test_abreviation_ne_coupe_pas():
    fragments = ["Le Dr. Martin vous reçoit.", ""]
    assert list(iter_sentences(fragments)) == ["Le Dr. Martin vous reçoit."]


def test_reste_sans_ponctuation_est_vide_a_la_fin():
    assert list(iter_sentences(["réponse sans point final"])) == [
        "réponse sans point final"
    ]


def test_coupure_forcee_sur_segment_trop_long():
    long = "mot " * 100  # aucune ponctuation
    phrases = list(iter_sentences([long], max_chars=40))
    assert len(phrases) >= 2
    assert all(len(p) <= 40 for p in phrases)


def test_deux_points_marque_une_borne():
    assert list(iter_sentences(["Une question : "])) == ["Une question :"]


async def _stream(items):
    for it in items:
        yield it


async def test_variante_async():
    out = [p async for p in aiter_sentences(_stream(["Salut", "! Ça va", " ?"]))]
    assert out == ["Salut!", "Ça va ?"]
