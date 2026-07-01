"""Métriques en mémoire (implémente Metrics, OBS-10.2).

Compteurs + agrégats de latence (count/avg/max). Aucune donnée clinique n'y transite.
Pour la prod multi-instance, exporter vers Prometheus via le même port.
"""

from __future__ import annotations

# Métriques de latence du pipeline live (LIVE-7.4 / OBS-10.2). Sert de référence au
# dashboard et au garde-fou de non-régression (cf. cibles ARCHITECTURE.md §5).
LIVE_LATENCY_METRICS = (
    "form_state_latency_ms",        # délai d'extraction après énoncé
    "endpoint_to_first_audio_ms",   # fin de parole → 1er son agent (spéculatif + TTS pipeliné)
    "backchannel_latency_ms",       # fin de parole → accusé immédiat
)


class InMemoryMetrics:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._samples: dict[str, dict[str, float]] = {}

    def incr(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value

    def observe(self, name: str, value_ms: float) -> None:
        s = self._samples.setdefault(name, {"count": 0.0, "sum": 0.0, "max": 0.0})
        s["count"] += 1
        s["sum"] += value_ms
        s["max"] = max(s["max"], value_ms)

    def snapshot(self) -> dict:
        latencies = {
            name: {
                "count": int(s["count"]),
                "avg_ms": round(s["sum"] / s["count"], 2) if s["count"] else 0.0,
                "max_ms": round(s["max"], 2),
            }
            for name, s in self._samples.items()
        }
        return {"counters": dict(self._counters), "latencies": latencies}
