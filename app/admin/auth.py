"""Authentification du portail admin."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.config import get_settings

_admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def verifier_admin_api(cle: str | None = Depends(_admin_key_header)) -> None:
    settings = get_settings()
    if cle is None or not secrets.compare_digest(cle, settings.admin_password):
        raise HTTPException(status_code=401, detail="Clé admin invalide.")
