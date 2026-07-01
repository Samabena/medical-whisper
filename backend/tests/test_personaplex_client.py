"""MODEL-6.3 — l'adapter PersonaPlex dialogue avec un vrai serveur WS (sans GPU).

Démarre un faux serveur `websockets` en mémoire qui parle notre protocole, puis pilote
`PersonaPlexClient` sur un tour complet. Valide l'ouverture, l'envoi et le décodage.
"""

from __future__ import annotations

import json

import websockets

from app.application.ports.speech_agent import AgentTurnEnd, AudioChunk, Transcript
from app.domain.value_objects import Language
from app.infrastructure.speech.personaplex_client import PersonaPlexClient


async def _fake_handler(ws):
    async for raw in ws:
        if isinstance(raw, (bytes, bytearray)):
            continue
        msg = json.loads(raw)
        if msg["type"] == "init":
            await ws.send(json.dumps({"type": "text", "speaker": "agent", "text": "Bonjour", "final": True}))
            await ws.send(b"\x00\x00")
            await ws.send(json.dumps({"type": "turn_end"}))
        elif msg["type"] == "end_turn":
            await ws.send(json.dumps({"type": "text", "speaker": "agent", "text": "OK", "final": True}))
            await ws.send(json.dumps({"type": "turn_end"}))


async def test_adapter_dialogue_complet():
    async with websockets.serve(_fake_handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = PersonaPlexClient(f"ws://localhost:{port}")
        session = await client.open(persona="p", voice="v", language=Language.FR)

        textes_agent: list[str] = []
        audios = 0
        fins = 0
        relance_envoyee = False

        async for ev in session.events():
            if isinstance(ev, Transcript):
                textes_agent.append(ev.text)
            elif isinstance(ev, AudioChunk):
                audios += 1
            elif isinstance(ev, AgentTurnEnd):
                fins += 1
                if fins == 1 and not relance_envoyee:
                    await session.send_audio(b"\x01\x02")
                    await session.end_user_turn()
                    relance_envoyee = True
                elif fins >= 2:
                    break

        await session.close()

    assert "Bonjour" in textes_agent   # tour d'ouverture
    assert "OK" in textes_agent         # réponse à la relance
    assert audios >= 1                  # audio binaire décodé en AudioChunk
