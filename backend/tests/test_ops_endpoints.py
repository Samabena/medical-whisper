"""OBS-10.2 — endpoint /metrics et usage admin."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.domain.entities import UsageRecord
from app.interface import deps
from app.interface.main import create_app
from tests.fakes import InMemoryUsageRepo


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "counters" in body and "latencies" in body


def test_usage_admin():
    usage = InMemoryUsageRepo()
    asyncio.run(usage.record(UsageRecord(account_id=1, endpoint="session_create")))
    asyncio.run(usage.record(UsageRecord(account_id=1, endpoint="session_create")))

    app = create_app()
    app.dependency_overrides[deps.usage_repo] = lambda: usage
    app.dependency_overrides[deps.require_admin] = lambda: "admin@local"
    client = TestClient(app)

    r = client.get("/admin/api/accounts/1/usage")
    assert r.status_code == 200
    assert r.json() == {"account_id": 1, "counts": {"session_create": 2}}
