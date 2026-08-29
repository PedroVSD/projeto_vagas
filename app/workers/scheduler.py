"""Fase 5 - Scheduler APScheduler: coleta periódica + digest diário.

Monólito modular: roda no mesmo container da API ou no worker dedicado.
Inicia automaticamente se SCHEDULER_ENABLED=true.
"""

from __future__ import annotations

import logging
import signal
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.workers.runner import run_digest, run_pipeline

setup_logging()
logger = logging.getLogger(__name__)


def start_scheduler(block: bool = True):
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("Scheduler desabilitado (SCHEDULER_ENABLED=false)")
        return None

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # Job 1: coleta periódica
    scheduler.add_job(
        run_pipeline,
        IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        id="pipeline",
        name=f"Pipeline a cada {settings.scheduler_interval_minutes}min",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info("Scheduler: pipeline a cada %s min", settings.scheduler_interval_minutes)

    # Job 2: digest diário (se habilitado)
    if settings.digest_enabled:
        try:
            hour, minute = map(int, settings.digest_time.split(":"))
            scheduler.add_job(
                run_digest,
                CronTrigger(hour=hour, minute=minute),
                id="digest",
                name=f"Digest diário {settings.digest_time}",
                replace_existing=True,
                max_instances=1,
            )
            logger.info("Scheduler: digest diário %s", settings.digest_time)
        except Exception as e:
            logger.warning("Digest time inválido %s: %s", settings.digest_time, e)

    scheduler.start()
    logger.info("Scheduler iniciado (APScheduler)")

    if settings.scheduler_collect_on_start:
        logger.info("Collect on start habilitado -> pipeline inicial")
        try:
            run_pipeline()
        except Exception as e:
            logger.warning("Pipeline inicial falhou: %s", e)

    if block:
        logger.info("Scheduler em modo blocking, Ctrl+C para sair")

        # Graceful shutdown
        def _handle(sig, frame):
            logger.info("Scheduler stopping...")
            scheduler.shutdown(wait=False)

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler parado")

    return scheduler


if __name__ == "__main__":
    start_scheduler(block=True)
