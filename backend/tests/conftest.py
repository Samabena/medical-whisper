"""Fixtures de test — secrets obligatoires + base SQLite async en mémoire."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Secrets requis par Settings : injectés avant toute importation de l'app.
# JWT_SECRET ≥ 32 caractères (validation de config, SEC-2.1).
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod-0123456789abcdef")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.infrastructure.config import get_settings
    from app.interface.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c


@pytest_asyncio.fixture
async def db_session():
    """Session async sur une base SQLite en mémoire (StaticPool = connexion partagée)."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.db.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()
