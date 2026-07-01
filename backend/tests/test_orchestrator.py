"""LIVE-7.2 — relais full-duplex : audio bidirectionnel, transcript, form_state, final."""

from __future__ import annotations

import asyncio

from app.application.live.connection import AudioFrame, ClientMessage, Closed, Control
from app.application.live.orchestrator import RunLiveDialogue
from app.domain.entities import (
    FieldValue,
    FormDefinition,
    FormField,
    FormState,
    LiveSession,
)
from app.domain.value_objects import Confidence, FieldType, SessionStatus
from app.infrastructure.observability.metrics import InMemoryMetrics
from app.infrastructure.results.memory_store import InMemorySessionResultStore
from app.infrastructure.speech.stub_agent import ScriptedTurn, StubSpeechAgent
from tests.fakes import InMemorySessionRepo


class FakeConnection:
    def __init__(self, inbound: list[ClientMessage]) -> None:
        self._in: asyncio.Queue[ClientMessage] = asyncio.Queue()
        for m in inbound:
            self._in.put_nowait(m)
        self.sent_json: list[dict] = []
        self.sent_audio: list[bytes] = []
        self.closed = False

    async def receive(self) -> ClientMessage:
        return await self._in.get()

    async def send_audio(self, data: bytes) -> None:
        self.sent_audio.append(data)

    async def send_json(self, msg: dict) -> None:
        self.sent_json.append(msg)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


class FakeExtractor:
    """Remplit `nom` dès que le transcript mentionne « Martin »."""

    async def update(self, transcript: str, form: FormDefinition, partiel: FormState) -> FormState:
        if "Martin" in transcript:
            partiel.values["nom"] = FieldValue("Martin", Confidence.CONFIANT)
        return partiel


async def test_dialogue_complet_jusqu_au_final():
    form = FormDefinition(
        account_id=1,
        form_id="consult",
        titre="Consultation",
        fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
    )
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)
    results = InMemorySessionResultStore()

    agent = StubSpeechAgent(script=[ScriptedTurn("Le patient s'appelle Martin", "Merci")])
    agent_session = await agent.open(persona="p", voice="v", language=form_langue())

    conn = FakeConnection([AudioFrame(b"\x01\x02"), Control({"type": "end_turn"})])

    metrics = InMemoryMetrics()
    uc = RunLiveDialogue(FakeExtractor(), results, sessions, metrics=metrics)
    await asyncio.wait_for(uc.execute(conn, agent_session, form, session), timeout=5)

    # Audio relayé dans les deux sens.
    assert agent_session.received_frames == [b"\x01\x02"]   # client → agent
    assert len(conn.sent_audio) >= 1                          # agent → client

    types = [m["type"] for m in conn.sent_json]
    assert "transcript" in types
    assert "form_state" in types
    final = next(m for m in conn.sent_json if m["type"] == "final")
    assert final["statut"] == "termine"
    assert final["form"]["nom"]["valeur"] == "Martin"

    # Résultat stocké + session marquée terminée + connexion fermée.
    stored = await results.get(session.id)
    assert stored["formulaire"]["nom"]["valeur"] == "Martin"
    assert session.statut is SessionStatus.COMPLETED
    assert conn.closed is True

    # Métriques instrumentées (OBS-10.2).
    snap = metrics.snapshot()
    assert snap["counters"]["sessions_completed"] == 1
    assert snap["counters"]["user_turns"] >= 1
    assert snap["latencies"]["form_state_latency_ms"]["count"] >= 1


async def test_tour_par_texte_remplit_le_formulaire():
    """Un message de contrôle user_text est traité comme un tour de parole."""
    form = FormDefinition(
        account_id=1, form_id="consult", titre="Consultation",
        fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
    )
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)
    results = InMemorySessionResultStore()

    agent = StubSpeechAgent()  # aucun script : le tour vient du texte client
    agent_session = await agent.open(persona="p", voice="v", language=form_langue())
    conn = FakeConnection([Control({"type": "user_text", "text": "le patient s'appelle Martin"})])

    uc = RunLiveDialogue(FakeExtractor(), results, sessions)
    await asyncio.wait_for(uc.execute(conn, agent_session, form, session), timeout=5)

    final = next(m for m in conn.sent_json if m["type"] == "final")
    assert final["statut"] == "termine"
    assert final["form"]["nom"]["valeur"] == "Martin"
    # L'écho du transcript utilisateur a bien été envoyé.
    assert any(m.get("type") == "transcript" and m.get("speaker") == "user" for m in conn.sent_json)


class _NoopExtractor:
    async def update(self, transcript, form, partiel):
        return partiel


class FakeTextAgent:
    """Agent piloté texte (capacité TextDrivenSession) : répond à chaque user_text."""

    def __init__(self) -> None:
        import asyncio as _aio

        from app.application.ports.speech_agent import AgentTurnEnd, Transcript

        self._q: _aio.Queue = _aio.Queue()
        self.user_texts: list[str] = []
        self._q.put_nowait(Transcript("Bonjour, j'écoute.", "agent", True))
        self._q.put_nowait(AgentTurnEnd())

    async def send_audio(self, frame: bytes) -> None:
        pass

    async def end_user_turn(self) -> None:
        pass

    async def send_user_text(self, text: str) -> None:
        from app.application.ports.speech_agent import AgentTurnEnd, Transcript

        self.user_texts.append(text)
        await self._q.put(Transcript("Et ensuite ?", "agent", True))
        await self._q.put(AgentTurnEnd())

    async def events(self):
        while True:
            ev = await self._q.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        await self._q.put(None)


async def test_user_text_transmis_a_l_agent_conversationnel():
    """Sans complétion, la réplique tapée est transmise à l'agent pour qu'il réponde."""
    form = FormDefinition(
        account_id=1, form_id="consult", titre="Consultation",
        fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
    )
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)

    agent = FakeTextAgent()
    conn = FakeConnection(
        [Control({"type": "user_text", "text": "bonjour"}), Control({"type": "stop"})]
    )

    uc = RunLiveDialogue(_NoopExtractor(), InMemorySessionResultStore(), sessions)
    await asyncio.wait_for(uc.execute(conn, agent, form, session), timeout=5)

    assert agent.user_texts == ["bonjour"]  # le texte a bien atteint l'agent


async def test_cloture_incomplet_apres_plafond_de_tours():
    form = FormDefinition(
        account_id=1,
        form_id="consult",
        titre="Consultation",
        fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
    )
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)
    results = InMemorySessionResultStore()

    agent = StubSpeechAgent(script=[ScriptedTurn("je ne sais pas", "d'accord")])
    agent_session = await agent.open(persona="p", voice="v", language=form_langue())
    conn = FakeConnection([Control({"type": "end_turn"})])

    uc = RunLiveDialogue(_NoopExtractor(), results, sessions, max_user_turns=1)
    await asyncio.wait_for(uc.execute(conn, agent_session, form, session), timeout=5)

    final = next(m for m in conn.sent_json if m["type"] == "final")
    assert final["statut"] == "incomplet"
    assert "nom" not in final["form"]  # champ requis non obtenu
    assert session.statut is SessionStatus.CLOSED
    assert (await results.get(session.id))["statut"] == "incomplet"


def form_langue():
    from app.domain.value_objects import Language

    return Language.FR
