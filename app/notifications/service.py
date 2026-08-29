"""Fase 4 - Serviço de notificação: roteia para adapters, persiste Notification."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job
from app.models.notification import Notification
from app.notifications.email import EmailProvider
from app.notifications.telegram import TelegramProvider

logger = logging.getLogger(__name__)


def get_enabled_providers() -> list:
    providers = []
    tg = TelegramProvider()
    if tg.is_enabled():
        providers.append(tg)
    em = EmailProvider()
    if em.is_enabled():
        providers.append(em)
    return providers


def should_notify(
    score: dict | None,
    threshold: int | None = None,
    immediate_threshold: int | None = None,
) -> tuple[bool, str]:
    if not score:
        return False, "sem score"
    s = get_settings()
    thr = threshold if threshold is not None else s.score_threshold
    imm = immediate_threshold if immediate_threshold is not None else s.immediate_threshold
    final = score.get("final_score", 0)
    if final >= imm:
        return True, "immediate"
    if final >= thr:
        return True, "digest"
    return False, "abaixo threshold"


def notify_job(
    db: Session, job: Job, score: dict, providers: list | None = None
) -> list[Notification]:
    """Cria e envia notificações para um job se atingir threshold. Retorna lista criada."""
    ok, mode = should_notify(score)
    if not ok:
        logger.debug("Job %s score %s não notificado: %s", job.id, score.get("final_score"), mode)
        return []

    if providers is None:
        providers = get_enabled_providers()
    if not providers:
        logger.info("Nenhum provider habilitado, criando notificações pendentes")
        # ainda cria registro pendente
        providers = []

    payload = {
        "title": job.title,
        "company": job.company.name if job.company else "Empresa",
        "company_name": job.company.name if job.company else "Empresa",
        "url": job.url,
        "location": job.location,
        "modality": job.modality,
        "seniority": job.seniority,
        "technologies": job.technologies,
        "first_seen_at": str(job.first_seen_at),
        "description": job.description,
        "score": score,
    }

    created: list[Notification] = []
    for p in providers:
        # evita duplicar envio já feito
        exists = (
            db.query(Notification)
            .filter(
                Notification.job_id == job.id,
                Notification.provider == p.name,
                Notification.status == "sent",
            )
            .first()
        )
        if exists:
            logger.debug("Job %s já notificado via %s", job.id, p.name)
            continue

        notif = Notification(
            job_id=job.id,
            provider=p.name,
            channel=getattr(p, "chat_id", None) or getattr(p, "smtp_to", None),
            payload=payload,
            status="pending",
        )
        db.add(notif)
        db.flush()

        sent = p.send(payload)
        notif.status = "sent" if sent else "failed"
        if sent:
            notif.sent_at = datetime.now(UTC)
        db.flush()
        created.append(notif)

    # se nenhum provider, cria um registro pending genérico para histórico
    if not providers:
        notif = Notification(
            job_id=job.id,
            provider="none",
            channel=None,
            payload=payload,
            status="pending",
        )
        db.add(notif)
        db.flush()
        created.append(notif)

    db.commit()
    return created


def build_digest(db: Session, limit: int = 5) -> dict[str, Any]:
    """Gera digest diário: estatísticas + top 5."""
    from app.models.job_score import JobScore

    total = db.query(Job).count()
    # novas nas últimas 24h? simplificado: total
    # altamente relevantes >=75, relevantes 60-74, descartadas <45
    highly = db.query(JobScore).filter(JobScore.final_score >= 75).count()
    relevant = (
        db.query(JobScore).filter(JobScore.final_score >= 60, JobScore.final_score < 75).count()
    )
    discarded = db.query(JobScore).filter(JobScore.final_score < 45).count()

    top = (
        db.query(Job, JobScore)
        .join(JobScore, Job.id == JobScore.job_id)
        .order_by(JobScore.final_score.desc())
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "highly_relevant": highly,
        "relevant": relevant,
        "discarded": discarded,
        "top": [
            {
                "title": j.title,
                "company": j.company.name if j.company else "",
                "score": s.final_score,
                "classification": s.classification,
                "url": j.url,
            }
            for j, s in top
        ],
    }
