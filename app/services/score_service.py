"""Fase 3/6 - Serviço de scoring: heuristic + LLM opcional.

Fase 6: LLM só para candidatas (heuristic >= threshold), JSON validado,
não controla pipeline diretamente. Suporta Ollama local/cloud ou OpenAI.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.job import Job
from app.models.job_score import JobScore
from app.scoring.heuristic import score_job

logger = logging.getLogger(__name__)


def score_and_persist(db: Session, job: Job) -> JobScore:
    job_dict = {
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "modality": job.modality,
        "seniority": job.seniority,
        "technologies": job.technologies,
    }
    result = score_job(job_dict)

    # Fase 6: LLM classificação para candidatas
    llm_score_val: int | None = None
    llm_payload: dict | None = None
    s = get_settings()
    # só chama LLM se habilitado, heuristic >= threshold e filtros passaram
    threshold = s.score_threshold
    if s.llm_enabled and result["heuristic_score"] >= threshold:
        try:
            from app.scoring.llm import get_llm_provider

            provider = get_llm_provider()
            if provider.is_enabled():
                # enriquece payload com campos que o LLM espera (§8)
                llm_job = {
                    "title": job.title,
                    "company": job.company.name if job.company else "",
                    "location": job.location,
                    "modality": job.modality,
                    "seniority": job.seniority,
                    "description": job.description,
                    "requirements": job.description,
                    "technologies": job.technologies,
                    "url": job.url,
                }
                llm_res = provider.classify(llm_job)
                if llm_res:
                    llm_score_val = llm_res.overall_match
                    llm_payload = llm_res.model_dump()
                    # final = média ponderada heuristic 70% + llm 30%
                    # LLM não controla diretamente, mas refina
                    final = int(round(result["heuristic_score"] * 0.7 + llm_score_val * 0.3))
                    result["final_score"] = max(0, min(100, final))
                    # se LLM recomendar ignore mas heuristic alto, mantém heuristic
                    if llm_res.recommendation == "ignore" and result["heuristic_score"] >= 75:
                        result["final_score"] = result["heuristic_score"]
                        logger.info(
                            "LLM recommend ignore mas heuristic alto, mantendo %s",
                            result["final_score"],
                        )
                    # anexa llm no breakdown para auditoria
                    result["llm"] = llm_payload
                    logger.info(
                        "LLM score job %s: heuristic %s -> final %s (llm %s)",
                        job.id,
                        result["heuristic_score"],
                        result["final_score"],
                        llm_score_val,
                    )
                else:
                    logger.debug("LLM sem retorno para job %s", job.id)
        except Exception as e:
            logger.warning("LLM classify falhou job %s: %s", job.id, e)

    existing = db.query(JobScore).filter(JobScore.job_id == job.id).first()
    if existing:
        existing.heuristic_score = result["heuristic_score"]
        existing.llm_score = llm_score_val
        existing.final_score = result["final_score"]
        existing.classification = result["classification"]
        existing.seniority_breakdown = result["seniority_breakdown"]
        existing.area_breakdown = result["area_breakdown"]
        existing.tech_breakdown = result["tech_breakdown"]
        existing.modality_breakdown = result["modality_breakdown"]
        existing.penalties = result["penalties"]
        # armazena llm payload no tech_breakdown para auditoria
        if llm_payload:
            existing.tech_breakdown = {**(result["tech_breakdown"] or {}), "llm": llm_payload}
        db.flush()
        return existing

    score = JobScore(
        job_id=job.id,
        heuristic_score=result["heuristic_score"],
        llm_score=llm_score_val,
        final_score=result["final_score"],
        classification=result["classification"],
        seniority_breakdown=result["seniority_breakdown"],
        area_breakdown=result["area_breakdown"],
        tech_breakdown=(
            result["tech_breakdown"]
            if not llm_payload
            else {**(result["tech_breakdown"] or {}), "llm": llm_payload}
        ),
        modality_breakdown=result["modality_breakdown"],
        penalties=result["penalties"],
    )
    db.add(score)
    db.flush()
    return score


def score_all_unscored(db: Session) -> int:
    jobs = (
        db.query(Job)
        .outerjoin(JobScore, Job.id == JobScore.job_id)
        .filter(JobScore.id.is_(None))
        .all()
    )
    for j in jobs:
        score_and_persist(db, j)
    db.commit()
    return len(jobs)
