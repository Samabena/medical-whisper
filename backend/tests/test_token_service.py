"""INT-5.1 — jetons éphémères JWT : émission, vérification, expiration, signature."""

from __future__ import annotations

import pytest

from app.domain.errors import UnauthorizedError
from app.infrastructure.security.jwt_tokens import JwtTokenService


def test_mint_puis_verify():
    svc = JwtTokenService("secret")
    tok = svc.mint("sess-1", 60)
    claims = svc.verify(tok.token)
    assert claims.session_id == "sess-1"
    assert claims.jti  # identifiant unique présent (anti-rejeu)


def test_jeton_expire_refuse():
    svc = JwtTokenService("secret")
    tok = svc.mint("sess-1", -5)  # exp dans le passé
    with pytest.raises(UnauthorizedError):
        svc.verify(tok.token)


def test_signature_invalide_refuse():
    tok = JwtTokenService("secret").mint("sess-1", 60)
    with pytest.raises(UnauthorizedError):
        JwtTokenService("autre-secret").verify(tok.token)
