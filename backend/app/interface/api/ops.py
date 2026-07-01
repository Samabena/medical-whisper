"""Endpoint d'observabilité (OBS-10.2) — métriques agrégées, sans donnée clinique."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.ports.metrics import Metrics
from app.interface import deps

router = APIRouter(tags=["Ops"])


@router.get("/metrics")
async def metrics(m: Metrics = Depends(deps.metrics)) -> dict:
    return m.snapshot()
