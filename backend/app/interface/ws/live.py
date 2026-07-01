"""Endpoint WebSocket live `/v1/live/{session_id}` (LIVE-7.1).

Authentifie le jeton éphémère (+ usage unique + Origin), charge compte/persona/voix/
langue/formulaire, ouvre l'agent vocal et délègue le relais full-duplex à l'orchestrateur.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, WebSocket

from app.application.live.connection import AudioFrame, ClientMessage, Closed, Control
from app.application.live.orchestrator import RunLiveDialogue
from app.application.ports.extractor import FormExtractorPort
from app.application.ports.metrics import Metrics
from app.application.ports.replay import ReplayGuard
from app.application.ports.repositories import AccountRepo, FormRepo, SessionRepo
from app.application.ports.result_store import SessionResultStore
from app.application.ports.speech_agent import SpeechAgentPort
from app.application.ports.token_service import EphemeralTokenPort
from app.domain.errors import UnauthorizedError
from app.infrastructure.config import Settings
from app.interface import deps

logger = logging.getLogger(__name__)
router = APIRouter()

# Codes de fermeture WebSocket applicatifs (4000-4999 = usage privé).
WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403
WS_NOT_FOUND = 4404


class StarletteClientConnection:
    """Adapter du WebSocket Starlette vers le port `ClientConnection`."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def receive(self) -> ClientMessage:
        msg = await self._ws.receive()
        if msg.get("type") == "websocket.disconnect":
            return Closed()
        if msg.get("bytes") is not None:
            return AudioFrame(msg["bytes"])
        if msg.get("text") is not None:
            try:
                return Control(json.loads(msg["text"]))
            except ValueError:
                return Control({})
        return Control({})

    async def send_audio(self, data: bytes) -> None:
        await self._ws.send_bytes(data)

    async def send_json(self, msg: dict) -> None:
        await self._ws.send_text(json.dumps(msg))

    async def close(self, code: int = 1000) -> None:
        await self._ws.close(code)


def _expiree(expires_at) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) > expires_at


@router.websocket("/v1/live/{session_id}")
async def live(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    tokens: EphemeralTokenPort = Depends(deps.token_service),
    replay: ReplayGuard = Depends(deps.replay_guard),
    sessions: SessionRepo = Depends(deps.session_repo),
    accounts: AccountRepo = Depends(deps.account_repo),
    forms: FormRepo = Depends(deps.form_repo),
    agent: SpeechAgentPort = Depends(deps.speech_agent),
    results: SessionResultStore = Depends(deps.result_store),
    extractor: FormExtractorPort = Depends(deps.extractor),
    metrics: Metrics = Depends(deps.metrics),
    config: Settings = Depends(deps.settings),
) -> None:
    # 1) Jeton : signature/expiration + correspondance session + usage unique.
    try:
        claims = tokens.verify(token)
    except UnauthorizedError:
        await websocket.close(code=WS_UNAUTHORIZED)
        return
    if claims.session_id != session_id:
        await websocket.close(code=WS_UNAUTHORIZED)
        return
    if not await replay.try_consume(claims.jti):
        await websocket.close(code=WS_UNAUTHORIZED)
        return

    # 2) Chargement session/compte/formulaire.
    session = await sessions.get(session_id)
    if session is None or _expiree(session.expires_at):
        await websocket.close(code=WS_NOT_FOUND)
        return
    account = await accounts.get(session.account_id)
    form = await forms.get(session.account_id, session.form_id)
    if account is None or not account.actif or form is None:
        await websocket.close(code=WS_NOT_FOUND)
        return

    # 3) Origin : allowlist par compte si définie, sinon allowlist globale.
    allowlist = account.allowed_origins or config.cors_origins
    if allowlist:
        if websocket.headers.get("origin") not in allowlist:
            await websocket.close(code=WS_FORBIDDEN)
            return

    # 4) Ouverture de l'agent vocal (persona/voix/langue résolues).
    await websocket.accept()
    langue = form.langue or account.langue
    from app.application.forms.prompt_builder import build_hotwords, build_persona

    persona = account.persona_prompt or build_persona(form)
    hotwords = build_hotwords(form)  # lexique du formulaire → biais STT (FORM-4.2)
    agent_session = await agent.open(
        persona=persona, voice=account.voice_prompt, language=langue, hotwords=hotwords
    )
    metrics.incr("ws_connections")

    conn = StarletteClientConnection(websocket)
    uc = RunLiveDialogue(
        extractor,
        results,
        sessions,
        max_user_turns=config.max_user_turns,
        metrics=metrics,
        speculative_trigger=config.speculative_trigger,
        barge_in=config.barge_in,
        backchannel=config.backchannel,
        backchannel_text=config.backchannel_text,
    )
    try:
        await uc.execute(conn, agent_session, form, session)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur dialogue live %s", session_id)
        try:
            await conn.send_json({"type": "error", "message": str(exc)})
            await conn.close()
        except Exception:  # noqa: BLE001
            pass
