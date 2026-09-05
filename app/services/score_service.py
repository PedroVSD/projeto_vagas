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

_last_llm_call: float = 0.0


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
    # só chama LLM se habilitado, heuristic >= threshold e filtros passaram + throttling (yaml throttling.llm_throttle_seconds tem prioridade)
    threshold = s.score_threshold
    if s.llm_enabled and result["heuristic_score"] >= threshold:
        import time
        from pathlib import Path

        import yaml

        global _last_llm_call
        # yaml tem prioridade sobre .env
        throttle = s.llm_throttle_seconds
        try:
            yp = Path("config/search_queries.yaml")
            if yp.exists():
                ydata = yaml.safe_load(yp.read_text(encoding="utf-8")) or {}
                throttle = ydata.get("throttling", {}).get("llm_throttle_seconds", throttle)
        except Exception:
            pass
        now = time.time()
        if throttle > 0 and now - _last_llm_call < throttle:
            wait = int(throttle - (now - _last_llm_call))
            logger.info(
                "LLM throttling: pulando LLM job %s (yaml %ss, aguardar %ss) - mantém heuristic",
                job.id,
                throttle,
                wait,
            )
            # pula LLM mas mantém pipeline rápido - telegram 1min continua
            llm_payload = None
        else:
            _last_llm_call = now
            try:
                from app.scoring.llm import get_llm_provider

                provider = get_llm_provider()
                if provider.is_enabled():
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
                        final = int(round(result["heuristic_score"] * 0.7 + llm_score_val * 0.3))
                        result["final_score"] = max(0, min(100, final))
                        if llm_res.recommendation == "ignore" and result["heuristic_score"] >= 75:
                            result["final_score"] = result["heuristic_score"]
                            logger.info(
                                "LLM recommend ignore mas heuristic alto, mantendo %s",
                                result["final_score"],
                            )
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
