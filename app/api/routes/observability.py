"""Fase 7 - Observabilidade: métricas, health detalhado, Prometheus."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.metrics import get_current_stats, prometheus_format

router = APIRouter(tags=["observability"])


@router.get("/metrics", summary="Métricas Prometheus (pronto para Grafana)")
def metrics():
    try:
        stats = get_current_stats()
        body = prometheus_format(stats)
        return Response(content=body, media_type="text/plain; version=0.0.4")
    except Exception as e:
        # sem DB ainda -> retorna erro controlado, não derruba pipeline
        return Response(content=f"# error collecting metrics: {e}\n", media_type="text/plain")


@router.get("/observability", summary="Estatísticas observabilidade (JSON)")
def observability(db: Session = Depends(get_db)):
    from app.core.metrics import get_current_stats

    try:
        stats = get_current_stats(db)
        return stats
    except Exception as e:
        return {"error": str(e), "jobs_total": 0}


@router.get("/health/detailed", summary="Health detalhado + métricas por fonte")
def health_detailed(db: Session = Depends(get_db)):
    checks = {}
    # DB
    try:
        db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"error: {e}"

    # LLM
    try:
        from app.scoring.llm import get_llm_provider

        p = get_llm_provider()
        checks["llm"] = {"provider": type(p).__name__, "enabled": p.is_enabled()}
    except Exception as e:
        checks["llm"] = f"error: {e}"

    # Scheduler
    from app.core.config import get_settings

    s = get_settings()
    checks["scheduler"] = {
        "enabled": s.scheduler_enabled,
        "interval_minutes": s.scheduler_interval_minutes,
        "digest_enabled": s.digest_enabled,
    }

    # Providers notificação
    checks["notifications"] = {
        "telegram": bool(s.telegram_bot_token and s.telegram_chat_id),
        "email": bool(s.smtp_host and s.smtp_to),
    }

    # Stats rápidas
    try:
        from app.core.metrics import get_current_stats

        stats = get_current_stats(db)
        checks["stats"] = {
            "jobs_total": stats["jobs_total"],
            "notifications_sent": stats["notifications_sent"],
        }
    except Exception:
        checks["stats"] = {}

    return checks
