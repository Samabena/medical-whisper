"""LIVE-7.1/7.2 — endpoint WebSocket live de bout en bout (auth jeton + dialogue stub)."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.domain.entities import (
    Account,
    FieldValue,
    FormDefinition,
    FormField,
    FormState,
    LiveSession,
)
from app.domain.value_objects import Confidence, FieldType, Language
from app.infrastructure.live.replay_guard import InMemoryReplayGuard
from app.infrastructure.results.memory_store import InMemorySessionResultStore
from app.infrastructure.security.jwt_tokens import JwtTokenService
from app.infrastructure.speech.stub_agent import ScriptedTurn, StubSpeechAgent
from app.interface import deps
from app.interface.main import create_app
from tests.fakes import InMemoryAccountRepo, InMemoryFormRepo, InMemorySessionRepo


class FakeExtractor:
    async def update(self, transcript: str, form: FormDefinition, partiel: FormState) -> FormState:
        if "Martin" in transcript:
            partiel.values["nom"] = FieldValue("Martin", Confidence.CONFIANT)
        return partiel


def _setup() -> SimpleNamespace:
    accounts, forms, sessions = InMemoryAccountRepo(), InMemoryFormRepo(), InMemorySessionRepo()
    results, replay = InMemorySessionResultStore(), InMemoryReplayGuard()
    tokens = JwtTokenService("x" * 40)

    async def go():
        account = await accounts.add(Account(nom="App", email_contact="a@ex.com", langue=Language.FR))
        await forms.add(
            FormDefinition(
                account_id=account.id,
                form_id="consult",
                titre="Consultation",
                fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
            )
        )
        session = LiveSession(account_id=account.id, form_id="consult")
        await sessions.add(session)
        return session

    session = asyncio.run(go())
    token = tokens.mint(session.id, 60).token

    app = create_app()
    app.dependency_overrides[deps.account_repo] = lambda: accounts
    app.dependency_overrides[deps.form_repo] = lambda: forms
    app.dependency_overrides[deps.session_repo] = lambda: sessions
    app.dependency_overrides[deps.result_store] = lambda: results
    app.dependency_overrides[deps.replay_guard] = lambda: replay
    app.dependency_overrides[deps.token_service] = lambda: tokens
    app.dependency_overrides[deps.extractor] = lambda: FakeExtractor()
    app.dependency_overrides[deps.speech_agent] = lambda: StubSpeechAgent(
        script=[ScriptedTurn("Le patient s'appelle Martin", "Merci")]
    )
    return SimpleNamespace(app=app, session=session, token=token, results=results)


def _recevoir_jusqu_au_final(ws, limite: int = 30) -> dict | None:
    for _ in range(limite):
        m = ws.receive()
        if m.get("bytes") is not None:
            continue  # audio agent
        texte = m.get("text")
        if texte:
            msg = json.loads(texte)
            if msg["type"] == "final":
                return msg
    return None


def test_dialogue_live_remplit_le_formulaire():
    s = _setup()
    client = TestClient(s.app)
    with client.websocket_connect(f"/v1/live/{s.session.id}?token={s.token}") as ws:
        ws.send_bytes(b"\x01\x02")
        ws.send_text(json.dumps({"type": "end_turn"}))
        final = _recevoir_jusqu_au_final(ws)

    assert final is not None
    assert final["form"]["nom"]["valeur"] == "Martin"
    assert asyncio.run(s.results.get(s.session.id))["formulaire"]["nom"]["valeur"] == "Martin"


def test_jeton_invalide_refuse():
    s = _setup()
    client = TestClient(s.app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/v1/live/{s.session.id}?token=mauvais") as ws:
            ws.receive()


def test_jeton_rejoue_refuse():
    s = _setup()
    client = TestClient(s.app)
    # 1er usage : OK.
    with client.websocket_connect(f"/v1/live/{s.session.id}?token={s.token}") as ws:
        ws.send_text(json.dumps({"type": "stop"}))
    # 2e usage du même jeton : refusé (anti-rejeu).
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/v1/live/{s.session.id}?token={s.token}") as ws:
            ws.receive()
