"""SEC-2.2 — en-têtes de sécurité et limitation de débit."""

from __future__ import annotations

import pytest

from app.infrastructure.cache.memory_rate_limiter import InMemoryRateLimiter


def test_entetes_de_securite_presents(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "Strict-Transport-Security" in r.headers
    assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    # API/admin : CSP stricte same-origin.
    assert r.headers["Content-Security-Policy"] == "default-src 'self'"


def test_csp_assouplie_sur_les_docs(client):
    """Régression : /docs doit autoriser les assets Swagger (CDN + script inline),
    sinon la page s'affiche blanche sous CSP stricte."""
    r = client.get("/docs")
    csp = r.headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in csp and "'unsafe-inline'" in csp
    # mais le reste de l'app garde la politique stricte
    assert client.get("/health").headers["Content-Security-Policy"] == "default-src 'self'"


async def test_rate_limiter_bloque_au_dela_du_seuil():
    limiter = InMemoryRateLimiter(limit=3)
    assert [await limiter.allow("ip-1") for _ in range(3)] == [True, True, True]
    assert await limiter.allow("ip-1") is False   # 4e refusée
    assert await limiter.allow("ip-2") is True     # autre clé indépendante
