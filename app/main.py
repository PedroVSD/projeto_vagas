import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.observability import router as observability_router
from app.api.routes.scoring import router as scoring_router
from app.api.routes.sources import router as sources_router
from app.api.routes.worker import router as worker_router
from app.core.config import get_settings
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="Job Finder API",
    description="Agente automatizado de busca, filtragem e notificação de vagas",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(sources_router)
app.include_router(notifications_router)
app.include_router(worker_router)
app.include_router(scoring_router)
app.include_router(observability_router)


@app.get("/", tags=["root"])
def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "env": settings.app_env,
        "docs": "/docs",
        "health": "/health",
    }


logger.info("App initialized env=%s debug=%s", settings.app_env, settings.debug)
