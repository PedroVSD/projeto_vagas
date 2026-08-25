"""Fase 5 - API worker/scheduler."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.workers.runner import run_digest, run_pipeline

router = APIRouter(prefix="/worker", tags=["worker"])


@router.get("/status", summary="Status do scheduler")
def status():
    s = get_settings()
    return {
        "scheduler_enabled": s.scheduler_enabled,
        "interval_minutes": s.scheduler_interval_minutes,
        "digest_enabled": s.digest_enabled,
        "digest_time": s.digest_time,
        "collect_on_start": s.scheduler_collect_on_start,
        "mode": "APScheduler (monólito modular) - Fase 5",
        "note": "Worker roda via docker compose --profile worker up ou scheduler local via python -m app.workers.scheduler",
    }


@router.post("/run", summary="Executa pipeline manualmente (coleta+scoring+notificação)")
def run():
    metrics = run_pipeline()
    return metrics


@router.post("/digest", summary="Executa digest manualmente")
def digest():
    data = run_digest()
    return data
