"""Fase 2 - API de fontes e ingestão."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.ingestion import ingest_all, ingest_source
from app.sources.registry import DEFAULT_SOURCES, get_source_by_name

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", summary="Lista fontes disponíveis")
def list_sources():
    return {
        "sources": [
            {"name": s.name, "description": s.__class__.__doc__ or ""}
            for s in DEFAULT_SOURCES
        ]
    }


@router.post("/ingest", summary="Ingere vagas de todas as fontes (ou específicas)")
def ingest(sources: list[str] | None = None, db: Session = Depends(get_db)):
    targets = DEFAULT_SOURCES
    if sources:
        targets = [s for s in DEFAULT_SOURCES if s.name in sources]
        if not targets:
            return {"error": f"nenhuma fonte encontrada para {sources}", "available": [s.name for s in DEFAULT_SOURCES]}
    results = ingest_all(db, targets)
    return {"results": results}


@router.post("/ingest/{source_name}", summary="Ingere vaga de uma fonte específica")
def ingest_one(source_name: str, db: Session = Depends(get_db)):
    src = get_source_by_name(source_name)
    if not src:
        return {"error": f"fonte '{source_name}' não encontrada", "available": [s.name for s in DEFAULT_SOURCES]}
    result = ingest_source(db, src)
    return result


@router.get("/preview/{source_name}", summary="Preview normalizado sem persistir (útil para testar)")
def preview(source_name: str):
    src = get_source_by_name(source_name)
    if not src:
        return {"error": f"fonte '{source_name}' não encontrada"}
    raws = src.fetch_jobs()
    norms = [src.normalize_job(r) for r in raws[:5]]
    return {
        "source": source_name,
        "collected": len(raws),
        "preview": [
            {
                "title": n.title,
                "company": n.company_name,
                "url": n.url,
                "location": n.location,
                "modality": n.modality,
                "seniority": n.seniority,
                "technologies": n.technologies,
                "fingerprint": n.fingerprint[:16] + "..." if n.fingerprint else None,
            }
            for n in norms
        ],
    }
