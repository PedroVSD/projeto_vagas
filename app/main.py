import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

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

# Fase 5 - Scheduler opcional dentro da API (monólito modular, sem precisar profile worker)
# Se SCHEDULER_ENABLED=true, inicia APScheduler em background no lifespan da API.
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    if settings.scheduler_enabled:
        try:
            from app.workers.scheduler import start_scheduler

            _scheduler = start_scheduler(block=False)
            logger.info("Scheduler iniciado no lifespan da API (Fase 5)")
        except Exception as e:
            logger.warning("Falha ao iniciar scheduler no lifespan: %s", e)
    yield
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("Scheduler parado no shutdown da API")
        except Exception:
            pass


app = FastAPI(
    title="Job Finder API",
    description="Agente automatizado de busca, filtragem e notificação de vagas",
    version="0.1.0",
    lifespan=lifespan,
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
        "frontend": "/ui",
    }


# Frontend simples (vanilla HTML/JS) — sem dependência extra (aiofiles)
_STATIC_DIR = Path(__file__).parent / "static"
_INDEX = _STATIC_DIR / "index.html"

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/ui", tags=["frontend"], include_in_schema=False)
def ui():
    if _INDEX.exists():
        return FileResponse(_INDEX, media_type="text/html")
    return {"error": "frontend not built", "expected": str(_INDEX)}


@app.get("/frontend", tags=["frontend"], include_in_schema=False)
def frontend():
    # alias para /ui
    if _INDEX.exists():
        return FileResponse(_INDEX, media_type="text/html")
    return RedirectResponse(url="/ui")


@app.get("/app", tags=["frontend"], include_in_schema=False)
def app_alias():
    return RedirectResponse(url="/ui")


logger.info("App initialized env=%s debug=%s", settings.app_env, settings.debug)
