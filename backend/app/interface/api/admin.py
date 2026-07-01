"""API d'administration — authentification (SEC-2.1).

Login par mot de passe → paire de jetons JWT (access court + refresh long).
`require_admin` (exporté via deps) protège les routes admin des EPICs 3/4.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.admin.auth import AdminAuthenticator
from app.application.ports.admin_tokens import AdminTokenService
from app.infrastructure.config import Settings
from app.interface import deps

router = APIRouter(prefix="/admin/api", tags=["Admin"])


class LoginRequete(BaseModel):
    password: str


class RefreshRequete(BaseModel):
    refresh_token: str


class TokensReponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessReponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokensReponse)
async def login(
    body: LoginRequete,
    auth: AdminAuthenticator = Depends(deps.admin_authenticator),
    tokens: AdminTokenService = Depends(deps.admin_token_service),
    config: Settings = Depends(deps.settings),
) -> TokensReponse:
    auth.authenticate(body.password)  # lève 401 si incorrect
    access, refresh = tokens.issue_pair(config.admin_email)
    return TokensReponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AccessReponse)
async def refresh(
    body: RefreshRequete,
    tokens: AdminTokenService = Depends(deps.admin_token_service),
) -> AccessReponse:
    return AccessReponse(access_token=tokens.refresh(body.refresh_token))


@router.get("/me")
async def me(admin: str = Depends(deps.require_admin)) -> dict:
    return {"admin": admin}
