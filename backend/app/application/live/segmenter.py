"""Segmenteur de phrases pour le TTS pipeliné (LIVE-7.4).

Le LLM agent produit sa réponse en **streaming** (token par token). Plutôt que
d'attendre la réponse complète avant de synthétiser, on découpe le flux en
**clauses/phrases** dès qu'une borne prosodique est atteinte, et on envoie chaque
phrase à la file TTS. Résultat : le **premier son** arrive bien plus tôt (le TTS
synthétise la 1ʳᵉ phrase pendant que l'agent génère la suite).

Module **pur** (aucune dépendance infra) : il transforme un flux de fragments texte
en un flux de phrases prêtes à synthétiser. Testable de façon déterministe.
"""

from __future__ import annotations

from typing import AsyncIterator, Iterable, Iterator

# Bornes de fin de phrase. Le « : » est inclus car il marque souvent une relance
# orale (« Une question : … »).
_SENTENCE_END = ".!?:…"

# Abréviations FR fréquentes : un point juste après ne clôt PAS la phrase. On
# compare en minuscules, sans le point final.
_ABBREVIATIONS = frozenset(
    {"dr", "pr", "m", "mme", "mlle", "mr", "etc", "cf", "p", "ex", "no", "n°"}
)


def _est_abreviation(buffer: str) -> bool:
    """Vrai si le dernier mot du buffer (avant le point) est une abréviation connue."""
    mot = buffer.rstrip(".").rsplit(None, 1)[-1] if buffer.rstrip(".") else ""
    return mot.lower() in _ABBREVIATIONS


def _coupe(buffer: str, max_chars: int) -> tuple[str | None, str]:
    """Tente d'extraire une phrase complète de `buffer`.

    Renvoie `(phrase, reste)`. `phrase` vaut `None` si aucune borne exploitable
    n'est encore présente. La longueur maxi `max_chars` force une coupure sur le
    dernier espace pour borner la latence même sans ponctuation.
    """
    for i, ch in enumerate(buffer):
        if ch in _SENTENCE_END:
            candidat = buffer[: i + 1]
            # Point d'abréviation (« Dr. ») ⇒ on continue d'accumuler.
            if ch == "." and _est_abreviation(candidat):
                continue
            return candidat.strip(), buffer[i + 1 :]

    if len(buffer) >= max_chars:
        # Pas de ponctuation mais segment trop long : couper au dernier espace.
        point = buffer.rfind(" ", 0, max_chars)
        if point > 0:
            return buffer[:point].strip(), buffer[point + 1 :]
    return None, buffer


def iter_sentences(fragments: Iterable[str], *, max_chars: int = 200) -> Iterator[str]:
    """Découpe un flux **synchrone** de fragments texte en phrases.

    Émet chaque phrase non vide dès qu'elle est complète ; vide le reste à la fin.
    """
    buffer = ""
    for fragment in fragments:
        buffer += fragment
        while True:
            phrase, buffer = _coupe(buffer, max_chars)
            if phrase is None:
                break
            if phrase:
                yield phrase
    reste = buffer.strip()
    if reste:
        yield reste


async def aiter_sentences(
    fragments: AsyncIterator[str], *, max_chars: int = 200
) -> AsyncIterator[str]:
    """Variante **asynchrone** : découpe le streaming de tokens de l'agent LLM.

    À brancher entre `LlmPort.repondre` (AsyncIterator[str]) et la file TTS.
    """
    buffer = ""
    async for fragment in fragments:
        buffer += fragment
        while True:
            phrase, buffer = _coupe(buffer, max_chars)
            if phrase is None:
                break
            if phrase:
                yield phrase
    reste = buffer.strip()
    if reste:
        yield reste
