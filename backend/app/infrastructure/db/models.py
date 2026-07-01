"""Tables SQLAlchemy 2.0 (DATA-1.3).

Ces modèles ORM sont **distincts** des entités du domaine : les repositories
convertissent ORM ↔ domaine (`mappers.py`). Le domaine ignore SQLAlchemy.
Les champs de formulaire sont stockés en JSON (JSONB en Postgres, JSON en SQLite).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class AccountORM(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    email_contact: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    langue: Mapped[str] = mapped_column(String(2), nullable=False, default="fr")
    persona_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allowed_origins: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    cles: Mapped[list["ApiKeyORM"]] = relationship(
        back_populates="compte", cascade="all, delete-orphan"
    )


class ApiKeyORM(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Clé principale")
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cree_a: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    compte: Mapped["AccountORM"] = relationship(back_populates="cles")


class FormDefinitionORM(Base):
    __tablename__ = "form_definitions"
    __table_args__ = (UniqueConstraint("account_id", "form_id", "version", name="uq_form_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    form_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False)
    langue: Mapped[str | None] = mapped_column(String(2), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class LiveSessionORM(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    form_id: Mapped[str] = mapped_column(String(120), nullable=False)
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    cree_a: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageRecordORM(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
