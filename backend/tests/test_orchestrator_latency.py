"""LIVE-7.4 — orchestrateur : déclenchement spéculatif, backchannel, barge-in."""

from __future__ import annotations

import asyncio

from app.application.live.connection import AudioFrame, ClientMessage, Control
from app.application.live.orchestrator import RunLiveDialogue
from app.application.ports.speech_agent import AudioChunk, SpeechEndpoint, Transcript
from app.domain.entities import FieldValue, FormDefinition, FormField, FormState, LiveSession
from app.domain.value_objects import Confidence, FieldType
from app.infrastructure.observability.metrics import InMemoryMetrics
from app.infrastructure.results.memory_store import InMemorySessionResultStore
from tests.fakes import InMemorySessionRepo


def _form() -> FormDefinition:
    return FormDefinition(
        account_id=1,
        form_id="consult",
        titre="Consultation",
        fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
    )


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
    async def update(self, transcript: str, form: FormDefinition, partiel: FormState) -> FormState:
        if "Martin" in transcript:
            partiel.values["nom"] = FieldValue("Martin", Confidence.CONFIANT)
        return partiel


class PartialThenEndpointAgent:
    """Émet un partiel STABLE puis un SpeechEndpoint, sans transcript final.

    Permet de vérifier que le déclenchement spéculatif agit sur le partiel stable
    sans attendre le final (LIVE-7.4).
    """

    def __init__(self) -> None:
        self._q: asyncio.Queue = asyncio.Queue()
        self._q.put_nowait(Transcript("le patient s'appelle Martin", "user", stable=True))
        self._q.put_nowait(SpeechEndpoint())

    async def send_audio(self, frame: bytes) -> None:
        pass

    async def end_user_turn(self) -> None:
        pass

    async def events(self):
        while True:
            ev = await self._q.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        await self._q.put(None)


async def test_declenchement_speculatif_sur_partiel_stable():
    form = _form()
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)
    results = InMemorySessionResultStore()
    metrics = InMemoryMetrics()

    agent = PartialThenEndpointAgent()
    conn = FakeConnection([])  # tout vient des événements agent
    uc = RunLiveDialogue(
        FakeExtractor(), results, sessions, metrics=metrics,
        speculative_trigger=True, backchannel=True,
    )
    await asyncio.wait_for(uc.execute(conn, agent, form, session), timeout=5)

    # Backchannel immédiat émis, puis complétion via le partiel stable (sans final).
    assert any(m["type"] == "backchannel" for m in conn.sent_json)
    final = next(m for m in conn.sent_json if m["type"] == "final")
    assert final["statut"] == "termine"
    assert final["form"]["nom"]["valeur"] == "Martin"
    assert metrics.snapshot()["counters"]["backchannel"] == 1


async def test_speculatif_desactive_attend_le_final():
    """Sans spéculatif, un simple partiel stable ne complète pas la session."""
    form = _form()
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)

    agent = PartialThenEndpointAgent()
    conn = FakeConnection([Control({"type": "stop"})])
    uc = RunLiveDialogue(
        FakeExtractor(), InMemorySessionResultStore(), sessions, speculative_trigger=False
    )
    await asyncio.wait_for(uc.execute(conn, agent, form, session), timeout=5)

    # Aucun form_state confiant émis depuis un partiel ⇒ pas de final « termine ».
    assert not any(m.get("type") == "final" and m.get("statut") == "termine" for m in conn.sent_json)


class TalkativeAgent:
    """Agent qui « parle » longtemps (plusieurs AudioChunks) — cible du barge-in."""

    def __init__(self) -> None:
        self._q: asyncio.Queue = asyncio.Queue()
        for _ in range(8):
            self._q.put_nowait(AudioChunk(b"\x00\x00"))

    async def send_audio(self, frame: bytes) -> None:
        pass

    async def end_user_turn(self) -> None:
        pass

    async def events(self):
        while True:
            ev = await self._q.get()
            if ev is None:
                return
            yield ev
            await asyncio.sleep(0.01)  # cadence l'émission

    async def close(self) -> None:
        await self._q.put(None)


class BargeInConnection:
    """Délivre une trame micro DÈS que l'agent commence à parler, puis stoppe."""

    def __init__(self) -> None:
        self.sent_json: list[dict] = []
        self.sent_audio: list[bytes] = []
        self.closed = False
        self._speaking = asyncio.Event()
        self._frame_sent = False

    async def receive(self) -> ClientMessage:
        if not self._frame_sent:
            await self._speaking.wait()  # attend que l'agent parle
            self._frame_sent = True
            return AudioFrame(b"\xaa")  # reprise de parole → barge-in
        await asyncio.sleep(0.05)
        return Control({"type": "stop"})

    async def send_audio(self, data: bytes) -> None:
        self.sent_audio.append(data)
        self._speaking.set()

    async def send_json(self, msg: dict) -> None:
        self.sent_json.append(msg)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


class _NoopExtractor:
    async def update(self, transcript, form, partiel):
        return partiel


async def test_barge_in_interrompt_l_agent():
    form = _form()
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)
    metrics = InMemoryMetrics()

    agent = TalkativeAgent()
    conn = BargeInConnection()
    uc = RunLiveDialogue(
        _NoopExtractor(), InMemorySessionResultStore(), sessions, metrics=metrics, barge_in=True
    )
    await asyncio.wait_for(uc.execute(conn, agent, form, session), timeout=5)

    # Une interruption a été signalée et l'audio agent restant a été coupé.
    assert any(m.get("type") == "interrupted" for m in conn.sent_json)
    assert metrics.snapshot()["counters"]["barge_in"] == 1
    assert len(conn.sent_audio) < 8  # tous les chunks n'ont pas été relayés
