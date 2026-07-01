"""Initialisation SQLAlchemy pour le module admin."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_engine = None
_SessionFactory = None


class Base(DeclarativeBase):
    pass


def _make_engine(database_url: str):
    if database_url == "sqlite:///:memory:":
        from sqlalchemy.pool import StaticPool
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(database_url, connect_args={"check_same_thread": False})


def get_engine():
    global _engine
    if _engine is None:
        from app.config import get_settings
        settings = get_settings()
        _engine = _make_engine(settings.database_url)
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False)
    return _SessionFactory


def creer_tables() -> None:
    from app.admin import models  # noqa: F401 — enregistre les modèles
    Base.metadata.create_all(bind=get_engine())


def reset_engine() -> None:
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def get_db() -> Generator[Session, None, None]:
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()
