from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.job import Job
from app.schemas.job import JobListResponse, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse, summary="Lista vagas")
def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    seniority: str | None = None,
    modality: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if seniority:
        query = query.filter(Job.seniority == seniority)
    if modality:
        query = query.filter(Job.modality == modality)

    total = query.count()
    items = query.order_by(Job.first_seen_at.desc()).offset(offset).limit(limit).all()
    return JobListResponse(items=items, total=total)


@router.get("/recommended", response_model=JobListResponse, summary="Vagas recomendadas")
def recommended_jobs(
    threshold: int = Query(default=60, ge=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Fase 1: sem scoring ainda - retorna todas ordenadas por data
    # Fase 3+ integrará com JobScore.final_score >= threshold
    from app.models.job_score import JobScore

    query = (
        db.query(Job)
        .join(JobScore, Job.id == JobScore.job_id)
        .filter(JobScore.final_score >= threshold)
    )
    total = query.count()
    items = query.order_by(JobScore.final_score.desc()).limit(limit).all()

    # Fallback: se não houver scores ainda, retorna lista vazia com mensagem implícita
    return JobListResponse(items=items, total=total)


@router.get("/{job_id}", response_model=JobResponse, summary="Detalhe da vaga")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/search/text", summary="Busca textual (placeholder Fase 3)")
def search_jobs(q: str = Query(..., min_length=2), db: Session = Depends(get_db)):
    # Fase 3: busca full-text; por enquanto ILIKE simples
    items = db.query(Job).filter(Job.title.ilike(f"%{q}%")).limit(20).all()
    return {"query": q, "items": items, "total": len(items)}
