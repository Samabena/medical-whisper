"""Modèles SQLAlchemy pour le portail admin B2B."""

from __future__ import annotations

import time

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.admin.database import Base


class ClientCompte(Base):
    __tablename__ = "client_comptes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    email_contact: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    date_creation: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    cles: Mapped[list["CleAPI"]] = relationship("CleAPI", back_populates="compte", cascade="all, delete-orphan")
    usages: Mapped[list["UsageLog"]] = relationship("UsageLog", back_populates="compte", cascade="all, delete-orphan")


class CleAPI(Base):
    __tablename__ = "cles_api"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    compte_id: Mapped[int] = mapped_column(Integer, ForeignKey("client_comptes.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Clé principale")
    cle_hachee: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cree_a: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    compte: Mapped["ClientCompte"] = relationship("ClientCompte", back_populates="cles")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    compte_id: Mapped[int] = mapped_column(Integer, ForeignKey("client_comptes.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    horodatage: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), nullable=False)

    compte: Mapped["ClientCompte"] = relationship("ClientCompte", back_populates="usages")
