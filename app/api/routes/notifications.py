"""Fase 4 - API de notificações."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.notification import Notification
from app.notifications.service import build_digest, get_enabled_providers

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", summary="Lista notificações")
def list_notifications(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Notification).order_by(Notification.created_at.desc())
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": n.id,
                "job_id": n.job_id,
                "provider": n.provider,
                "status": n.status,
                "sent_at": n.sent_at,
                "created_at": n.created_at,
                "payload": n.payload,
            }
            for n in items
        ],
    }


@router.get("/digest", summary="Digest diário (preview)")
def digest_preview(db: Session = Depends(get_db)):
    return build_digest(db)


@router.post("/test", summary="Envio de teste (mockado se sem credenciais)")
def test_notification(payload: dict | None = None, db: Session = Depends(get_db)):
    providers = get_enabled_providers()
    if not providers:
        return {
            "enabled": False,
            "message": "Nenhum provider habilitado (configure TELEGRAM_BOT_TOKEN/CHAT_ID ou SMTP). Payload de exemplo seria enviado.",
            "example_payload": payload or {"title": "Teste", "company": "Demo", "url": "https://example.com"},
        }

    test_payload = payload or {
        "title": "Junior Data Engineer — Teste",
        "company": "Empresa Demo",
        "url": "https://example.com/jobs/test",
        "location": "Brasil - Remoto",
        "modality": "remoto_brasil",
        "seniority": "junior",
        "technologies": ["Python", "SQL", "Airflow"],
        "score": {"final_score": 87, "classification": "muito_relevante", "area_breakdown": {"area": "data_engineering"}},
    }
    results = {}
    for p in providers:
        results[p.name] = p.send(test_payload)

    return {"enabled": True, "results": results, "providers": [p.name for p in providers]}


@router.get("/providers", summary="Lista providers e status")
def list_providers():
    from app.core.config import get_settings

    s = get_settings()
    return {
        "telegram": {"enabled": bool(s.telegram_bot_token and s.telegram_chat_id)},
        "email": {"enabled": bool(s.smtp_host and s.smtp_to)},
    }
