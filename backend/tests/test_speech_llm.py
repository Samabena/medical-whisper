"""MODEL-6.4 — agent conversationnel piloté par LLM (dev sans GPU).

Tests hors réseau : un faux client Ollama remplace l'AsyncClient réel.
"""

from __future__ import annotations

from app.application.ports.speech_agent import (
    AgentTurnEnd,
    SpeechError,
    TextDrivenSession,
    Transcript,
)
from app.domain.value_objects import Language
from app.infrastructure.speech.llm_agent import LlmSpeechSession


class FakeOllama:
    """Faux AsyncClient : renvoie des réponses scriptées et mémorise les messages reçus."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[dict]] = []

    async def chat(self, model: str, messages: list[dict], options=None):
        self.calls.append([dict(m) for m in messages])
        return {"message": {"content": self._replies.pop(0)}}


class BoomOllama:
    async def chat(self, *a, **k):
        raise RuntimeError("ollama down")


async def _drain_turn(session: LlmSpeechSession) -> list[Transcript]:
    """Consomme les événements jusqu'au prochain AgentTurnEnd (ou erreur)."""
    out: list[Transcript] = []
    async for ev in session.events():
        if isinstance(ev, Transcript):
            out.append(ev)
        elif isinstance(ev, SpeechError):
            out.append(ev)  # type: ignore[arg-type]
            break
        elif isinstance(ev, AgentTurnEnd):
            break
    return out


def _session(client) -> LlmSpeechSession:
    return LlmSpeechSession(client=client, model="m", persona="Persona test.", language=Language.FR)


async def test_ouverture_emet_salutation():
    fake = FakeOllama(["Bonjour, quel est le nom du patient ?"])
    session = _session(fake)
    await session._ouvrir()

    evts = await _drain_turn(session)
    assert [e.speaker for e in evts] == ["agent"]
    assert evts[0].text == "Bonjour, quel est le nom du patient ?"
    # L'amorce interne ne doit PAS rester dans l'historique de conversation.
    assert all("Commence la conversation" not in m["content"] for m in session._messages)
    # Le système (persona) est conservé.
    assert session._messages[0]["role"] == "system"


async def test_tour_utilisateur_genere_une_reponse_contextuelle():
    fake = FakeOllama(["Bonjour !", "Merci, et quel âge a-t-il ?"])
    session = _session(fake)
    await session._ouvrir()
    await _drain_turn(session)

    await session.send_user_text("Le patient s'appelle Jean.")
    evts = await _drain_turn(session)
    assert evts[0].text == "Merci, et quel âge a-t-il ?"
    # Le texte utilisateur a bien été transmis au LLM.
    dernier_appel = fake.calls[-1]
    assert {"role": "user", "content": "Le patient s'appelle Jean."} in dernier_appel


async def test_texte_vide_ignore():
    fake = FakeOllama(["Bonjour !"])
    session = _session(fake)
    await session._ouvrir()
    await _drain_turn(session)
    n = len(fake.calls)
    await session.send_user_text("   ")
    assert len(fake.calls) == n  # aucun appel supplémentaire


async def test_panne_llm_remonte_une_erreur_propre():
    session = _session(BoomOllama())
    await session._ouvrir()
    evts = await _drain_turn(session)
    assert isinstance(evts[0], SpeechError)


async def test_session_est_text_driven():
    """L'orchestrateur reconnaît la capacité texte par isinstance (Protocol structurel)."""
    assert isinstance(_session(FakeOllama([])), TextDrivenSession)
