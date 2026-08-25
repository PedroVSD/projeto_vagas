"""Fase 7 - Métricas observabilidade (§16) + pronto para Prometheus/Grafana.

Métricas básicas: collected, new, duplicates, discarded, sent, elapsed, errors by source.
Armazenadas em memória (últimas 100 execuções) + consulta DB para totais atuais.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.job import Job
from app.models.job_score import JobScore
from app.models.notification import Notification

# Histórico em memória (últimas 100)
_history: deque[dict[str, Any]] = deque(maxlen=100)


def record_run(metrics: dict[str, Any]) -> None:
    metrics["timestamp"] = time.time()
    _history.append(metrics)


def get_history(limit: int = 10) -> list[dict[str, Any]]:
    return list(_history)[-limit:]


def get_current_stats(db: Session | None = None) -> dict[str, Any]:
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        total = db.query(Job).count()
        scored = db.query(JobScore).count()
        sent = db.query(Notification).filter(Notification.status == "sent").count()
        failed = db.query(Notification).filter(Notification.status == "failed").count()
        pending = db.query(Notification).filter(Notification.status == "pending").count()

        # por classificação
        excelente = db.query(JobScore).filter(JobScore.classification == "excelente").count()
        muito = db.query(JobScore).filter(JobScore.classification == "muito_relevante").count()
        relevante = db.query(JobScore).filter(JobScore.classification == "relevante").count()
        talvez = db.query(JobScore).filter(JobScore.classification == "talvez_relevante").count()
        ignorar = db.query(JobScore).filter(JobScore.classification == "ignorar").count()

        return {
            "jobs_total": total,
            "jobs_scored": scored,
            "notifications_sent": sent,
            "notifications_failed": failed,
            "notifications_pending": pending,
            "by_classification": {
                "excelente": excelente,
                "muito_relevante": muito,
                "relevante": relevante,
                "talvez_relevante": talvez,
                "ignorar": ignorar,
            },
            "recent_runs": get_history(5),
        }
    finally:
        if close:
            db.close()


def prometheus_format(stats: dict[str, Any]) -> str:
    """Formato Prometheus text exposition (para futuro Grafana)."""
    lines = [
        "# HELP job_finder_jobs_total Total de vagas no banco",
        "# TYPE job_finder_jobs_total gauge",
        f"job_finder_jobs_total {stats['jobs_total']}",
        "# HELP job_finder_jobs_scored Vagas com score",
        "# TYPE job_finder_jobs_scored gauge",
        f"job_finder_jobs_scored {stats['jobs_scored']}",
        "# HELP job_finder_notifications_sent Notificações enviadas",
        "# TYPE job_finder_notifications_sent counter",
        f"job_finder_notifications_sent {stats['notifications_sent']}",
        "# HELP job_finder_notifications_failed Notificações falhas",
        "# TYPE job_finder_notifications_failed counter",
        f"job_finder_notifications_failed {stats['notifications_failed']}",
    ]
    for cls, val in stats["by_classification"].items():
        lines.append(f'job_finder_by_classification{{classification="{cls}"}} {val}')
    return "\n".join(lines) + "\n"
