"""CORE-0.1 — l'app démarre et /health répond 200."""

from __future__ import annotations


def test_health_ok(client):
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok"}
