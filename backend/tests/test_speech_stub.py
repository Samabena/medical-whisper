"""MODEL-6.2 — l'agent vocal stub déroule un dialogue scripté déterministe (sans GPU)."""

from __future__ import annotations

from app.application.ports.speech_agent import AgentTurnEnd, AudioChunk, Transcript
from app.infrastructure.speech.stub_agent import ScriptedTurn, StubSpeechAgent
from app.domain.value_objects import Language


async def _lire_tour(session) -> list:
    """Collecte les événements jusqu'au prochain `AgentTurnEnd` inclus."""
    batch = []
    async for ev in session.events():
        batch.append(ev)
        if isinstance(ev, AgentTurnEnd):
            return batch
    return batch


async def test_ouverture_salue_dans_la_langue():
    agent = StubSpeechAgent()
    session = await agent.open(persona="assistant", voice="v", language=Language.EN)
    ouverture = await _lire_tour(session)
    textes = [e.text for e in ouverture if isinstance(e, Transcript)]
    assert "Hello, I'm listening." in textes
    assert any(isinstance(e, AudioChunk) for e in ouverture)


async def test_dialogue_scripte():
    script = [ScriptedTurn(user_text="Le patient s'appelle Martin", agent_text="Quel est le motif ?")]
    agent = StubSpeechAgent(script=script)
    session = await agent.open(persona="p", voice="v", language=Language.FR)

    await _lire_tour(session)  # consomme l'ouverture

    await session.send_audio(b"\x01\x02")
    await session.end_user_turn()
    tour = await _lire_tour(session)

    transcripts = [e for e in tour if isinstance(e, Transcript)]
    assert transcripts[0].speaker == "user" and "Martin" in transcripts[0].text
    assert transcripts[1].speaker == "agent" and "motif" in transcripts[1].text
    assert session.received_frames == [b"\x01\x02"]  # l'audio utilisateur est bien reçu

    await session.close()
