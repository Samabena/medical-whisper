"""Faux serveur WebSocket PersonaPlex (MODEL-6.2 — conteneur dev).

Parle le protocole JSON+binaire de `app/infrastructure/speech/protocol.py` pour
permettre de tester l'adapter `PersonaPlexClient` SANS GPU. Reçoit l'`init`, puis à
chaque `end_turn` renvoie une réponse d'agent scriptée (texte + audio factice + turn_end).

Lancé par docker-compose (profil dev). Aucune dépendance au reste de l'app.
"""

from __future__ import annotations

import asyncio
import json
import os

import websockets

_SILENCE = b"\x00\x00" * 240
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8998"))


async def handler(ws) -> None:
    langue = "fr"
    async for raw in ws:
        if isinstance(raw, (bytes, bytearray)):
            continue  # trame audio entrante : ignorée par le faux serveur
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        if msg.get("type") == "init":
            langue = msg.get("language", "fr")
            salut = "Bonjour, je vous écoute." if langue == "fr" else "Hello, I'm listening."
            await ws.send(json.dumps({"type": "text", "speaker": "agent", "text": salut, "final": True}))
            await ws.send(_SILENCE)
            await ws.send(json.dumps({"type": "turn_end"}))
        elif msg.get("type") == "end_turn":
            reponse = "Très bien, c'est noté." if langue == "fr" else "All right, noted."
            await ws.send(json.dumps({"type": "text", "speaker": "agent", "text": reponse, "final": True}))
            await ws.send(_SILENCE)
            await ws.send(json.dumps({"type": "turn_end"}))


async def main() -> None:
    print(f"[model-stub] faux serveur PersonaPlex sur ws://{HOST}:{PORT}", flush=True)
    async with websockets.serve(handler, HOST, PORT, max_size=None):
        await asyncio.Future()  # tourne indéfiniment


if __name__ == "__main__":
    asyncio.run(main())
