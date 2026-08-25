"""Fase 5 - Runner: pipeline Collect → Scoring → Notification (monólito modular).

Usado pelo scheduler e via CLI/API manual.
Justificativa APScheduler (README § Decisões): mais simples que Celery+Redis para MVP,
sem broker externo, in-process, fácil teste. Celery entra só se escalar para workers distribuídos.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.sources.registry import DEFAULT_SOURCES
from app.services.ingestion import ingest_all

logger = logging.getLogger(__name__)


def run_pipeline(sources: list | None = None) -> dict[str, Any]:
    """Executa pipeline completo e retorna métricas.

    Pipeline (Fase 5): cada fonte -> fetch -> normalize -> dedup -> score -> notify
    (scoring e notificação já ocorrem dentro de ingest_all via ingest_source).
    """
    start = time.time()
    sources = sources or DEFAULT_SOURCES
    source_names = [s.name for s in sources]
    logger.info("Pipeline start sources=%s", source_names)

    db: Session = SessionLocal()
    try:
        results = ingest_all(db, sources)

        # Métricas agregadas
        total_collected = sum(r.get("collected", 0) for r in results)
        total_new = sum(r.get("new", 0) for r in results)
        total_dup = sum(r.get("duplicates", 0) for r in results)
        total_err = sum(r.get("errors", 0) for r in results)

        # Observabilidade (§16 - Fase 7)
        # jobs scored já via ingestion; contar notificações e por fonte
        from app.core.metrics import record_run
        from app.models.notification import Notification

        try:
            sent = db.query(Notification).filter(Notification.status == "sent").count()
        except Exception:
            sent = 0

        elapsed = round(time.time() - start, 2)
        # erros por fonte
        errors_by_source = {r["source"]: r.get("errors", 0) for r in results}
        metrics = {
            "collected": total_collected,
            "new": total_new,
            "duplicates": total_dup,
            "discarded": max(0, total_collected - total_new - total_dup),
            "errors": total_err,
            "errors_by_source": errors_by_source,
            "notifications_sent": sent,
            "elapsed_s": elapsed,
            "sources": results,
        }
        # logging estruturado (Fase 7) - não expõe secrets
        logger.info("Pipeline done metrics=%s", metrics, extra={"metrics": metrics})
        try:
            record_run(metrics)
        except Exception:
            pass
        return metrics
    except Exception as e:
        logger.exception("Pipeline falhou: %s", e)
        return {"error": str(e), "elapsed_s": round(time.time() - start, 2)}
    finally:
        db.close()


def run_digest() -> dict[str, Any]:
    """Gera e envia digest diário (08:00)."""
    from app.core.database import SessionLocal
    from app.notifications.service import build_digest, get_enabled_providers
    from app.notifications.formatting import format_job_message

    db = SessionLocal()
    try:
        digest = build_digest(db, limit=5)
        providers = get_enabled_providers()
        if not providers:
            logger.info("Digest: nenhum provider habilitado, apenas log")
            logger.info("Digest %s", digest)
            return digest

        # Formata digest para envio
        top_lines = "\n".join(
            f"- {j['title']} — {j['company']} [{j['score']}/100] {j['url']}" for j in digest["top"]
        )
        text = f"""Digest Diário Job Finder — {digest['total']} vagas no banco
{digest['highly_relevant']} altamente relevantes (>=75)
{digest['relevant']} relevantes (60-74)
{digest['discarded']} descartadas (<45)

Top 5:
{top_lines if top_lines else "Nenhuma vaga relevante ainda."}
"""
        payload = {
            "title": "Digest Diário — Job Finder",
            "company": "Job Finder",
            "url": "http://localhost:8000/jobs/recommended",
            "description": text,
            "technologies": [],
            "score": {"final_score": 0, "classification": "digest"},
        }
        for p in providers:
            try:
                p.send(payload)
            except Exception as e:
                logger.warning("Digest send falhou %s: %s", p.name, e)

        logger.info("Digest enviado %s", digest)
        return digest
    finally:
        db.close()
