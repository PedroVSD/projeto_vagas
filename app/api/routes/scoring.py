"""Fase 6 - API scoring + LLM."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models.job import Job

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.get("/llm/status", summary="Status LLM provider")
def llm_status():
    from app.scoring.llm import get_llm_provider

    s = get_settings()
    p = get_llm_provider()
    return {
        "llm_enabled": s.llm_enabled,
        "llm_provider": s.llm_provider,
        "provider_class": type(p).__name__,
        "is_enabled": p.is_enabled(),
        "ollama_base_url": s.ollama_base_url,
        "ollama_model": s.ollama_model,
        "has_ollama_api_key": bool(s.ollama_api_key),
        "openai_model": s.openai_model,
        "has_openai_key": bool(s.openai_api_key),
        "note": (
            "LLM só é chamado para vagas candidatas "
            "(heuristic >= score_threshold) - custo controlado"
        ),
    }


@router.post("/llm/classify", summary="Classifica vaga com LLM (sem persistir)")
def llm_classify(payload: dict):
    from app.scoring.llm import get_llm_provider

    provider = get_llm_provider()
    if not provider.is_enabled():
        raise HTTPException(status_code=400, detail="LLM desabilitado (configure OLLAMA ou OPENAI)")

    # payload deve ter title, company, location, etc.
    result = provider.classify(payload)
    if not result:
        raise HTTPException(status_code=502, detail="LLM falhou ou retornou inválido")

    return result.model_dump()


@router.post("/recompute/{job_id}", summary="Recomputa score heurístico + LLM para um job")
def recompute(job_id: int, db: Session = Depends(get_db)):
    from app.services.score_service import score_and_persist

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    score = score_and_persist(db, job)
    db.commit()
    return {
        "job_id": job.id,
        "heuristic_score": score.heuristic_score,
        "llm_score": score.llm_score,
        "final_score": score.final_score,
        "classification": score.classification,
    }


@router.post("/recompute-all", summary="Recomputa scores de vagas sem score")
def recompute_all(db: Session = Depends(get_db)):
    from app.services.score_service import score_all_unscored

    count = score_all_unscored(db)
    return {"recomputed": count}
