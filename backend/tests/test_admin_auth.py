"""SEC-2.1 — hachage argon2, authenticator admin, jetons access/refresh."""

from __future__ import annotations

import pytest

from app.application.admin.auth import AdminAuthenticator
from app.domain.errors import UnauthorizedError
from app.infrastructure.security.admin_tokens import JwtAdminTokenService
from app.infrastructure.security.passwords import Argon2PasswordHasher

_SECRET = "k" * 40


def test_argon2_hash_et_verify():
    ph = Argon2PasswordHasher()
    h = ph.hash("s3cr3t")
    assert h != "s3cr3t"               # haché, pas en clair
    assert ph.verify(h, "s3cr3t") is True
    assert ph.verify(h, "mauvais") is False
    assert ph.verify("pas-un-hash", "s3cr3t") is False


def test_authenticator_depuis_plaintext():
    auth = AdminAuthenticator(Argon2PasswordHasher(), plaintext="motdepasse")
    assert auth.verify("motdepasse") is True
    assert auth.verify("autre") is False
    auth.authenticate("motdepasse")  # ne lève pas
    with pytest.raises(UnauthorizedError):
        auth.authenticate("autre")


def test_authenticator_sans_mot_de_passe_refuse_tout():
    auth = AdminAuthenticator(Argon2PasswordHasher())
    assert auth.verify("") is False
    assert auth.verify("quoi") is False


def test_jetons_access_refresh():
    svc = JwtAdminTokenService(_SECRET, access_ttl_minutes=30, refresh_ttl_days=7)
    access, refresh = svc.issue_pair("admin@local")
    assert svc.verify_access(access) == "admin@local"

    # Un refresh ne doit pas passer pour un access.
    with pytest.raises(UnauthorizedError):
        svc.verify_access(refresh)

    # Échange refresh → nouvel access valide.
    nouvel_access = svc.refresh(refresh)
    assert svc.verify_access(nouvel_access) == "admin@local"

    # Un access ne peut pas servir de refresh.
    with pytest.raises(UnauthorizedError):
        svc.refresh(access)


def test_jeton_invalide_refuse():
    svc = JwtAdminTokenService(_SECRET)
    with pytest.raises(UnauthorizedError):
        svc.verify_access("pas-un-jwt")
