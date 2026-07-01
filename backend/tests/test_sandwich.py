"""VOX-6 / LIVE-7.2 — agent sandwich (STT+agent+TTS) via l'orchestrateur réel."""

from __future__ import annotations

import asyncio

from app.application.live.connection import AudioFrame, ClientMessage, Control
from app.application.live.orchestrator import RunLiveDialogue
from app.application.ports.speech_agent import AgentTurnEnd, AudioChunk, SpeechEndpoint, Transcript
from app.domain.entities import FieldValue, FormDefinition, FormField, FormState, LiveSession
from app.domain.value_objects import Confidence, FieldType, Language
from app.infrastructure.results.memory_store import InMemorySessionResultStore
from app.infrastructure.speech.reply import ScriptedReply
from app.infrastructure.speech.sandwich import SandwichSpeechAgent
from app.infrastructure.stt.stub import StubSttStream
from app.infrastructure.tts.stub import StubTts
from tests.fakes import InMemorySessionRepo


def _form() -> FormDefinition:
    return FormDefinition(
        account_id=1,
        form_id="consult",
        titre="Consultation",
        fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
    )


def _sandwich(utterances, replies) -> SandwichSpeechAgent:
    return SandwichSpeechAgent(
        stt_stream=StubSttStream(utterances=utterances),
        tts=StubTts(),
        reply_factory=lambda persona, language: ScriptedReply(replies=replies, greeting="Bonjour"),
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


async def test_sandwich_remplit_le_formulaire_de_bout_en_bout():
    form = _form()
    session = LiveSession(account_id=1, form_id="consult")
    sessions = InMemorySessionRepo()
    await sessions.add(session)
    results = InMemorySessionResultStore()

    agent = _sandwich(["le patient s'appelle Martin"], ["Merci, c'est noté."])
    agent_session = await agent.open(persona="assistant clinique", voice="fr", language=Language.FR)

    conn = FakeConnection([AudioFrame(b"\x01\x02"), Control({"type": "end_turn"})])
    uc = RunLiveDialogue(
        FakeExtractor(), results, sessions, speculative_trigger=True, backchannel=True
    )
    await asyncio.wait_for(uc.execute(conn, agent_session, form, session), timeout=5)

    # L'audio micro a traversé STT ; l'agent a produit de l'audio (greeting + réponse).
    assert len(conn.sent_audio) >= 1
    # Backchannel émis (levier de latence), formulaire complété via le sandwich.
    assert any(m["type"] == "backchannel" for m in conn.sent_json)
    final = next(m for m in conn.sent_json if m["type"] == "final")
    assert final["statut"] == "termine"
    assert final["form"]["nom"]["valeur"] == "Martin"
    assert (await results.get(session.id))["formulaire"]["nom"]["valeur"] == "Martin"


async def test_sandwich_transmet_les_hotwords_de_session_au_stt():
    """FORM-4.2 : les hotwords passés à open() priment et atteignent le STT."""
    stt = StubSttStream(utterances=[])
    agent = SandwichSpeechAgent(
        stt_stream=stt,
        tts=StubTts(),
        reply_factory=lambda persona, language: ScriptedReply(greeting="Bonjour"),
        hotwords=["repli"],  # repli si la session n'en fournit pas
    )
    session = await agent.open(
        persona="p", voice="v", language=Language.FR, hotwords=["dyspnée", "tension"]
    )
    await session.close()
    assert stt.last_language is Language.FR
    assert stt.last_hotwords == ["dyspnée", "tension"]  # session prioritaire sur le repli


async def test_sandwich_replie_sur_les_hotwords_de_lagent_sans_session():
    stt = StubSttStream(utterances=[])
    agent = SandwichSpeechAgent(
        stt_stream=stt,
        tts=StubTts(),
        reply_factory=lambda persona, language: ScriptedReply(greeting="Bonjour"),
        hotwords=["repli"],
    )
    session = await agent.open(persona="p", voice="v", language=Language.FR)
    await session.close()
    assert stt.last_hotwords == ["repli"]


async def test_sandwich_mappe_les_evenements_stt_vers_le_port_agent():
    """Vérifie le mapping : partiel stable, endpoint, final user, puis réplique agent."""
    agent = _sandwich(["bonjour le patient"], ["Très bien."])
    session = await agent.open(persona="p", voice="v", language=Language.FR)

    collected = []

    async def drain():
        async for ev in session.events():
            collected.append(ev)

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.02)  # laisse l'ouverture s'émettre
    await session.end_user_turn()  # déclenche STT → agent
    await asyncio.sleep(0.05)
    await session.close()
    await asyncio.wait_for(task, timeout=2)

    user_partials = [
        e for e in collected if isinstance(e, Transcript) and e.speaker == "user" and e.stable
    ]
    user_finals = [
        e for e in collected if isinstance(e, Transcript) and e.speaker == "user" and e.is_final
    ]
    agent_texts = [e for e in collected if isinstance(e, Transcript) and e.speaker == "agent"]
    assert user_partials and user_partials[0].text == "bonjour le patient"
    assert any(isinstance(e, SpeechEndpoint) for e in collected)
    assert user_finals and user_finals[0].text == "bonjour le patient"
    assert agent_texts  # l'agent a parlé
    assert any(isinstance(e, AudioChunk) for e in collected)
    assert any(isinstance(e, AgentTurnEnd) for e in collected)
