"""OBS-10.1 / OBS-10.2 — métriques, rétention courte, audit non-PHI, logging structuré."""

from __future__ import annotations

import json
import logging

from app.infrastructure.db.models import LiveSessionORM, UsageRecordORM
from app.infrastructure.observability.logging import JsonFormatter
from app.infrastructure.observability.metrics import LIVE_LATENCY_METRICS, InMemoryMetrics
from app.infrastructure.results.memory_store import InMemorySessionResultStore


def test_metrics_compteurs_et_latence():
    m = InMemoryMetrics()
    m.incr("ws_connections")
    m.incr("ws_connections")
    m.observe("form_state_latency_ms", 100)
    m.observe("form_state_latency_ms", 200)
    snap = m.snapshot()
    assert snap["counters"]["ws_connections"] == 2
    assert snap["latencies"]["form_state_latency_ms"] == {"count": 2, "avg_ms": 150.0, "max_ms": 200.0}


def test_metriques_de_latence_live_agregees():
    """Les mesures de latence par étape (LIVE-7.4) s'agrègent comme attendu."""
    m = InMemoryMetrics()
    for name in LIVE_LATENCY_METRICS:
        m.observe(name, 500)
        m.observe(name, 1500)
    snap = m.snapshot()
    for name in LIVE_LATENCY_METRICS:
        assert snap["latencies"][name] == {"count": 2, "avg_ms": 1000.0, "max_ms": 1500.0}


async def test_resultat_purge_apres_ttl():
    expire = InMemorySessionResultStore(ttl_seconds=-1)  # déjà expiré
    await expire.save("s1", {"statut": "termine", "formulaire": {}})
    assert await expire.get("s1") is None  # donnée de santé purgée

    garde = InMemorySessionResultStore(ttl_seconds=600)
    await garde.save("s2", {"statut": "termine"})
    assert await garde.get("s2") is not None


def test_aucune_colonne_de_donnee_clinique():
    interdit = {"transcript", "audio", "content", "formulaire", "valeur", "patient", "texte"}
    for model in (LiveSessionORM, UsageRecordORM):
        colonnes = {c.name for c in model.__table__.columns}
        assert not (colonnes & interdit), f"{model.__name__} expose une colonne clinique"


def test_logging_json_sans_contenu():
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "session ouverte", None, None)
    rec.session_id = "abc"
    sortie = json.loads(JsonFormatter().format(rec))
    assert sortie["level"] == "INFO"
    assert sortie["msg"] == "session ouverte"
    assert sortie["session_id"] == "abc"
