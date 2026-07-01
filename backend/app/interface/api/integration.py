"""API d'intégration cliente — server-to-server (EPIC 5).

- POST /v1/integration/sessions          → crée une session live + jeton éphémère.
- GET  /v1/integration/sessions/{id}/result → récupère le formulaire final.

Auth par `X-API-Key` (résolu en compte). Le frontend du client ouvre ensuite le
WebSocket `ws_url` avec le `token` (EPIC 7) — la clé API ne quitte jamais son backend.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.application.forms.schema import form_schema
from app.application.integration.forms import GetPublishedForm, ListPublishedForms
from app.application.integration.get_result import GetSessionResult
from app.application.integration.start_session import StartLiveSession
from app.application.ports.repositories import FormRepo, SessionRepo, UsageRepo
from app.application.ports.result_store import SessionResultStore
from app.application.ports.token_service import EphemeralTokenPort
from app.domain.entities import Account, UsageRecord
from app.infrastructure.config import Settings
from app.interface import deps

router = APIRouter(prefix="/v1/integration", tags=["Intégration"])


class CreerSessionRequete(BaseModel):
    form_id: str


class CreerSessionReponse(BaseModel):
    session_id: str
    ws_url: str
    token: str
    language: str
    expires_at: datetime
    form_schema: dict


def _ws_url(request: Request, session_id: str) -> str:
    scheme = "wss" if request.url.scheme == "https" else "ws"
    return f"{scheme}://{request.url.netloc}/v1/live/{session_id}"


@router.get("/forms")
async def lister_formulaires(
    account: Account = Depends(deps.current_account),
    forms: FormRepo = Depends(deps.form_repo),
) -> list[dict]:
    items = await ListPublishedForms(forms).execute(account.id)
    return [{"form_id": f.form_id, "titre": f.titre} for f in items]


@router.get("/forms/{form_id}")
async def schema_formulaire(
    form_id: str,
    account: Account = Depends(deps.current_account),
    forms: FormRepo = Depends(deps.form_repo),
) -> dict:
    form = await GetPublishedForm(forms).execute(account.id, form_id)
    return form_schema(form)


@router.post("/sessions", status_code=201, response_model=CreerSessionReponse)
async def creer_session(
    body: CreerSessionRequete,
    request: Request,
    account: Account = Depends(deps.current_account),
    forms: FormRepo = Depends(deps.form_repo),
    sessions: SessionRepo = Depends(deps.session_repo),
    tokens: EphemeralTokenPort = Depends(deps.token_service),
    usage: UsageRepo = Depends(deps.usage_repo),
    config: Settings = Depends(deps.settings),
) -> CreerSessionReponse:
    uc = StartLiveSession(forms, sessions, tokens, config.session_token_ttl_seconds)
    res = await uc.execute(account, body.form_id)
    # Usage : métadonnée de facturation uniquement (aucune donnée clinique).
    await usage.record(UsageRecord(account_id=account.id, endpoint="session_create"))
    return CreerSessionReponse(
        session_id=res.session_id,
        ws_url=_ws_url(request, res.session_id),
        token=res.token,
        language=res.language,
        expires_at=res.expires_at,
        form_schema=res.form_schema,
    )


@router.get("/sessions/{session_id}/result")
async def recuperer_resultat(
    session_id: str,
    account: Account = Depends(deps.current_account),
    sessions: SessionRepo = Depends(deps.session_repo),
    results: SessionResultStore = Depends(deps.result_store),
) -> dict:
    uc = GetSessionResult(sessions, results)
    return await uc.execute(account, session_id)
