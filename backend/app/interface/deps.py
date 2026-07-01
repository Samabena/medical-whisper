"""Composition root — câblage des adapters vers les ports (DI FastAPI).

Centralise l'instanciation : repos request-scoped (une `AsyncSession` partagée par
requête grâce au cache de dépendances de FastAPI), services singletons, et résolution
du compte courant depuis la clé API.
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncIterator

from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.admin.auth import AdminAuthenticator
from app.application.integration.authenticate import authenticate_api_key
from app.application.ports.admin_tokens import AdminTokenService
from app.application.ports.extractor import FormExtractorPort
from app.application.ports.metrics import Metrics
from app.application.ports.rate_limiter import RateLimiter
from app.application.ports.replay import ReplayGuard
from app.application.ports.security import PasswordHasher
from app.application.ports.repositories import (
    AccountRepo,
    ApiKeyRepo,
    FormRepo,
    SessionRepo,
    UsageRepo,
)
from app.application.ports.result_store import SessionResultStore
from app.application.ports.security import KeyHasher
from app.application.ports.speech_agent import SpeechAgentPort
from app.application.ports.token_service import EphemeralTokenPort
from app.domain.entities import Account
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db.engine import get_sessionmaker
from app.infrastructure.db.repositories import (
    SqlAccountRepo,
    SqlApiKeyRepo,
    SqlFormRepo,
    SqlSessionRepo,
    SqlUsageRepo,
)
from app.application.forms.extractor import FormExtractor
from app.infrastructure.cache.memory_rate_limiter import InMemoryRateLimiter
from app.infrastructure.extraction.factory import build_flat_extractor
from app.infrastructure.live.replay_guard import InMemoryReplayGuard
from app.infrastructure.observability.metrics import InMemoryMetrics
from app.infrastructure.security.admin_tokens import JwtAdminTokenService
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.results.memory_store import InMemorySessionResultStore
from app.infrastructure.security.hashing import Sha256KeyHasher
from app.infrastructure.security.jwt_tokens import JwtTokenService
from app.infrastructure.speech.factory import build_speech_agent


def settings() -> Settings:
    return get_settings()


# --- Singletons --------------------------------------------------------------
@lru_cache
def speech_agent() -> SpeechAgentPort:
    return build_speech_agent(get_settings())


@lru_cache
def token_service() -> EphemeralTokenPort:
    return JwtTokenService(get_settings().jwt_secret)


@lru_cache
def result_store() -> SessionResultStore:
    return InMemorySessionResultStore(get_settings().result_retention_seconds)


@lru_cache
def metrics() -> Metrics:
    return InMemoryMetrics()


@lru_cache
def key_hasher() -> KeyHasher:
    return Sha256KeyHasher()


@lru_cache
def replay_guard() -> ReplayGuard:
    return InMemoryReplayGuard()


@lru_cache
def extractor() -> FormExtractorPort:
    """Extraction structurée : logique applicative + backend LLM configurable (null/ollama)."""
    return FormExtractor(build_flat_extractor(get_settings()))


@lru_cache
def password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


@lru_cache
def admin_authenticator() -> AdminAuthenticator:
    s = get_settings()
    return AdminAuthenticator(password_hasher(), s.admin_password_hash, s.admin_password)


@lru_cache
def admin_token_service() -> AdminTokenService:
    s = get_settings()
    return JwtAdminTokenService(s.jwt_secret, s.admin_access_ttl_minutes, s.admin_refresh_ttl_days)


@lru_cache
def rate_limiter() -> RateLimiter:
    return InMemoryRateLimiter(get_settings().rate_limit_per_minute)


_bearer = HTTPBearer(auto_error=False)


async def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    tokens: AdminTokenService = Depends(admin_token_service),
) -> str:
    from app.domain.errors import UnauthorizedError

    if creds is None:
        raise UnauthorizedError("Jeton admin manquant.")
    return tokens.verify_access(creds.credentials)


# --- Repos request-scoped ----------------------------------------------------
async def db_session() -> AsyncIterator[AsyncSession]:
    maker = get_sessionmaker()
    async with maker() as session:
        yield session


def account_repo(session: AsyncSession = Depends(db_session)) -> AccountRepo:
    return SqlAccountRepo(session)


def apikey_repo(session: AsyncSession = Depends(db_session)) -> ApiKeyRepo:
    return SqlApiKeyRepo(session)


def form_repo(session: AsyncSession = Depends(db_session)) -> FormRepo:
    return SqlFormRepo(session)


def session_repo(session: AsyncSession = Depends(db_session)) -> SessionRepo:
    return SqlSessionRepo(session)


def usage_repo(session: AsyncSession = Depends(db_session)) -> UsageRepo:
    return SqlUsageRepo(session)


# --- Compte courant (auth clé API) ------------------------------------------
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def current_account(
    cle: str | None = Depends(_api_key_header),
    accounts: AccountRepo = Depends(account_repo),
    keys: ApiKeyRepo = Depends(apikey_repo),
    hasher: KeyHasher = Depends(key_hasher),
) -> Account:
    return await authenticate_api_key(cle, accounts, keys, hasher)
