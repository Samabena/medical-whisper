"""API admin — comptes, langue, persona/voix, clés API (EPIC 3). Protégé par require_admin."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.admin.accounts import (
    CreateAccount,
    GetAccount,
    ListAccounts,
    UpdateAccount,
)
from app.application.admin.api_keys import CreateApiKey, ListApiKeys, RevokeApiKey
from app.application.ports.repositories import AccountRepo, ApiKeyRepo, UsageRepo
from app.application.ports.security import KeyHasher
from app.domain.entities import Account, ApiKey
from app.domain.value_objects import Language
from app.interface import deps

router = APIRouter(
    prefix="/admin/api", tags=["Admin · Comptes"], dependencies=[Depends(deps.require_admin)]
)


# --- Schémas --------------------------------------------------------------
class AccountCreate(BaseModel):
    nom: str
    email_contact: str
    langue: Language = Language.FR
    allowed_origins: list[str] = []


class AccountUpdate(BaseModel):
    nom: str | None = None
    langue: Language | None = None
    persona_prompt: str | None = None
    voice_prompt: str | None = None
    allowed_origins: list[str] | None = None
    actif: bool | None = None


class AccountOut(BaseModel):
    id: int
    nom: str
    email_contact: str
    langue: Language
    persona_prompt: str
    voice_prompt: str
    actif: bool
    allowed_origins: list[str]
    date_creation: datetime


class KeyCreate(BaseModel):
    label: str = "Clé principale"


class KeyOut(BaseModel):
    id: int
    label: str
    key_masquee: str
    actif: bool
    cree_a: datetime


class KeyCreatedOut(BaseModel):
    id: int
    label: str
    cle_en_clair: str   # affichée UNE seule fois
    actif: bool
    cree_a: datetime


def _account_out(a: Account) -> AccountOut:
    return AccountOut(
        id=a.id,
        nom=a.nom,
        email_contact=a.email_contact,
        langue=a.langue,
        persona_prompt=a.persona_prompt,
        voice_prompt=a.voice_prompt,
        actif=a.actif,
        allowed_origins=a.allowed_origins,
        date_creation=a.date_creation,
    )


def _key_out(k: ApiKey) -> KeyOut:
    return KeyOut(id=k.id, label=k.label, key_masquee=f"{k.key_prefix}…", actif=k.actif, cree_a=k.cree_a)


# --- Comptes --------------------------------------------------------------
@router.post("/accounts", status_code=201, response_model=AccountOut)
async def creer_compte(body: AccountCreate, accounts: AccountRepo = Depends(deps.account_repo)):
    compte = await CreateAccount(accounts).execute(
        body.nom, body.email_contact, body.langue, body.allowed_origins
    )
    return _account_out(compte)


@router.get("/accounts", response_model=list[AccountOut])
async def lister_comptes(accounts: AccountRepo = Depends(deps.account_repo)):
    return [_account_out(a) for a in await ListAccounts(accounts).execute()]


@router.get("/accounts/{account_id}", response_model=AccountOut)
async def obtenir_compte(account_id: int, accounts: AccountRepo = Depends(deps.account_repo)):
    return _account_out(await GetAccount(accounts).execute(account_id))


@router.patch("/accounts/{account_id}", response_model=AccountOut)
async def modifier_compte(
    account_id: int, body: AccountUpdate, accounts: AccountRepo = Depends(deps.account_repo)
):
    compte = await UpdateAccount(accounts).execute(
        account_id,
        nom=body.nom,
        langue=body.langue,
        persona_prompt=body.persona_prompt,
        voice_prompt=body.voice_prompt,
        allowed_origins=body.allowed_origins,
        actif=body.actif,
    )
    return _account_out(compte)


# --- Clés API -------------------------------------------------------------
@router.post("/accounts/{account_id}/keys", status_code=201, response_model=KeyCreatedOut)
async def creer_cle(
    account_id: int,
    body: KeyCreate = KeyCreate(),
    accounts: AccountRepo = Depends(deps.account_repo),
    keys: ApiKeyRepo = Depends(deps.apikey_repo),
    hasher: KeyHasher = Depends(deps.key_hasher),
):
    res = await CreateApiKey(accounts, keys, hasher).execute(account_id, body.label)
    return KeyCreatedOut(
        id=res.key.id,
        label=res.key.label,
        cle_en_clair=res.cle_claire,
        actif=res.key.actif,
        cree_a=res.key.cree_a,
    )


@router.get("/accounts/{account_id}/keys", response_model=list[KeyOut])
async def lister_cles(account_id: int, keys: ApiKeyRepo = Depends(deps.apikey_repo)):
    return [_key_out(k) for k in await ListApiKeys(keys).execute(account_id)]


@router.delete("/accounts/{account_id}/keys/{key_id}", response_model=KeyOut)
async def revoquer_cle(
    account_id: int, key_id: int, keys: ApiKeyRepo = Depends(deps.apikey_repo)
):
    return _key_out(await RevokeApiKey(keys).execute(account_id, key_id))


# --- Usage (métadonnées de facturation, OBS-10.2) -------------------------
@router.get("/accounts/{account_id}/usage")
async def usage_compte(account_id: int, usage: UsageRepo = Depends(deps.usage_repo)) -> dict:
    counts = await usage.count_by_endpoint(account_id)
    return {"account_id": account_id, "counts": counts}
