"""Engine & sessions SQLAlchemy async (DATA-1.3).

L'URL provient de la config. `creer_schema()` (create_all) sert aux tests ;
en prod, c'est Alembic qui applique le schéma (`alembic upgrade head`).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.config import get_settings
from app.infrastructure.db.models import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, future=True, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def creer_schema() -> None:
    """Crée toutes les tables (tests / bootstrap). Prod : préférer Alembic."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def reset_engine() -> None:
    """Réinitialise l'engine (tests : bascule d'URL, isolation)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
