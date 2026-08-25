"""Fase 3 - Serviço de scoring: aplica heuristic + opcional LLM."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

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

    existing = db.query(JobScore).filter(JobScore.job_id == job.id).first()
    if existing:
        existing.heuristic_score = result["heuristic_score"]
        existing.final_score = result["final_score"]
        existing.classification = result["classification"]
        existing.seniority_breakdown = result["seniority_breakdown"]
        existing.area_breakdown = result["area_breakdown"]
        existing.tech_breakdown = result["tech_breakdown"]
        existing.modality_breakdown = result["modality_breakdown"]
        existing.penalties = result["penalties"]
        db.flush()
        return existing

    score = JobScore(
        job_id=job.id,
        heuristic_score=result["heuristic_score"],
        final_score=result["final_score"],
        classification=result["classification"],
        seniority_breakdown=result["seniority_breakdown"],
        area_breakdown=result["area_breakdown"],
        tech_breakdown=result["tech_breakdown"],
        modality_breakdown=result["modality_breakdown"],
        penalties=result["penalties"],
    )
    db.add(score)
    db.flush()
    return score


def score_all_unscored(db: Session) -> int:
    jobs = db.query(Job).outerjoin(JobScore, Job.id == JobScore.job_id).filter(JobScore.id.is_(None)).all()
    for j in jobs:
        score_and_persist(db, j)
    db.commit()
    return len(jobs)
