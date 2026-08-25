"""Fase 2 - Ingestão: coleta -> normalização -> deduplicação -> persistência.

Pipeline: fetch_jobs() -> normalize_job() -> fingerprint -> upsert Job/Company
Evita duplicatas (mesma vaga múltiplas fontes = único registro, atualiza last_seen_at).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job
from app.models.job_source import JobSource as JobSourceModel
from app.sources.base import JobSource

logger = logging.getLogger(__name__)


def _get_or_create_company(db: Session, name: str) -> Company:
    c = db.query(Company).filter(Company.name == name).first()
    if c:
        return c
    c = Company(name=name)
    db.add(c)
    db.flush()
    return c


def _get_or_create_source_model(db: Session, source: JobSource) -> JobSourceModel:
    m = db.query(JobSourceModel).filter(JobSourceModel.name == source.name).first()
    if m:
        return m
    m = JobSourceModel(name=source.name, enabled=True, config={})
    db.add(m)
    db.flush()
    return m


def ingest_source(db: Session, source: JobSource) -> dict:
    """Ingere uma fonte, retorna métricas da execução."""
    source_model = _get_or_create_source_model(db, source)
    raws = source.fetch_jobs()
    collected = len(raws)

    new = 0
    updated = 0
    duplicates = 0
    errors = 0

    for raw in raws:
        try:
            norm = source.normalize_job(raw)
            if not norm.fingerprint:
                from app.services.deduplication import build_fingerprint

                norm.fingerprint = build_fingerprint(
                    norm.company_name, norm.title, norm.location, norm.url, norm.description
                )

            # Deduplicação: busca por fingerprint ou url
            existing = db.query(Job).filter(Job.fingerprint == norm.fingerprint).first()
            if existing is None:
                existing = db.query(Job).filter(Job.url == norm.url).first()

            company = _get_or_create_company(db, norm.company_name)

            if existing:
                # Atualiza se mudou
                existing.last_seen_at = datetime.now(timezone.utc)
                existing.updated_at = datetime.now(timezone.utc)
                if norm.description and norm.description != existing.description:
                    existing.description = norm.description
                if norm.technologies:
                    existing.technologies = norm.technologies
                # re-score ao atualizar
                try:
                    from app.services.score_service import score_and_persist

                    db.flush()
                    score_and_persist(db, existing)
                except Exception as se:
                    logger.warning("Scoring falhou para job %s: %s", existing.id, se)
                duplicates += 1
                updated += 1
            else:
                job = Job(
                    fingerprint=norm.fingerprint,
                    title=norm.title,
                    company_id=company.id,
                    source_id=source_model.id,
                    url=norm.url,
                    description=norm.description,
                    location=norm.location,
                    modality=norm.modality,
                    seniority=norm.seniority,
                    technologies=norm.technologies,
                    raw_payload=norm.raw_payload,
                )
                db.add(job)
                db.flush()
                # Fase 3: scoring heurístico imediato
                try:
                    from app.services.score_service import score_and_persist

                    score_and_persist(db, job)
                except Exception as se:
                    logger.warning("Scoring falhou para novo job %s: %s", norm.title, se)
                new += 1
        except Exception as e:
            logger.exception("Erro ao ingerir job %s: %s", raw.url if raw else "?", e)
            errors += 1
            continue

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Commit ingest falhou source=%s: %s", source.name, e)
        errors += 1

    # atualiza last_run_at
    source_model.last_run_at = datetime.now(timezone.utc)
    db.commit()

    metrics = {
        "source": source.name,
        "collected": collected,
        "new": new,
        "duplicates": duplicates,
        "updated": updated,
        "errors": errors,
    }
    logger.info("Ingest %s: %s", source.name, metrics)
    return metrics


def ingest_all(db: Session, sources: list[JobSource]) -> list[dict]:
    results: list[dict] = []
    for s in sources:
        try:
            results.append(ingest_source(db, s))
        except Exception as e:
            logger.exception("Fonte %s falhou completamente: %s", s.name, e)
            results.append({"source": s.name, "collected": 0, "new": 0, "duplicates": 0, "errors": 1, "error": str(e)})
    return results
