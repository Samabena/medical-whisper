"""Port de métriques (OBS-10.2). Compteurs + observations de latence, sans aucune donnée clinique."""

from __future__ import annotations

from typing import Protocol


class Metrics(Protocol):
    def incr(self, name: str, value: int = 1) -> None: ...
    def observe(self, name: str, value_ms: float) -> None: ...
    def snapshot(self) -> dict: ...
