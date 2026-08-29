"""Fase 2 - Primeira fonte legítima: Arbeitnow API.

API pública e gratuita: https://www.arbeitnow.com/api/job-board-api
- Sem auth, sem scraping, ToS permite uso via API.
- Retorna JSON com licensa aberta, ideal para MVP.
- Foco: vagas internacionais + remotas; filtramos por Júnior/Estágio via normalize.
- Alternativas já preparadas (Greenhouse, Lever) podem ser adicionadas sem mudar pipeline.
"""

from __future__ import annotations

import logging

import httpx

from app.services.deduplication import build_fingerprint
from app.services.normalization import (
    extract_modality,
    extract_seniority,
    extract_technologies,
    normalize_text,
)
from app.sources.base import JobSource, NormalizedJob, RawJob

logger = logging.getLogger(__name__)

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
TIMEOUT = 15


class ArbeitnowSource(JobSource):
    name = "arbeitnow"

    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as c:
                r = c.get(ARBEITNOW_URL, headers={"User-Agent": "job-finder/0.1"})
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning("Arbeitnow fetch falhou: %s", e)
            return []

        jobs = data.get("data") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            logger.warning("Arbeitnow formato inesperado: %s", type(data))
            return []

        raws: list[RawJob] = []
        for j in jobs:
            # campos: slug, company_name, title, description, remote,
            # url, tags, job_types, location, created_at
            title = j.get("title") or "Sem título"
            company = j.get("company_name") or "Desconhecida"
            url = j.get("url") or f"https://www.arbeitnow.com/jobs/{j.get('slug', '')}"
            slug = j.get("slug") or url
            raws.append(
                RawJob(
                    external_id=str(slug),
                    title=str(title),
                    company_name=str(company),
                    url=str(url),
                    description=j.get("description"),
                    location=j.get("location") or ("Remote" if j.get("remote") else None),
                    raw_payload=j,
                )
            )
        logger.info("Arbeitnow fetch: %d vagas", len(raws))
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location)
        # tags ajudam na extração de tech
        tags = raw.raw_payload.get("tags") or []
        full_text = f"{title} {desc or ''} {' '.join(tags)} {loc or ''}"
        techs = extract_technologies(full_text)
        seniority = extract_seniority(title, desc)
        modality = extract_modality(loc, desc)
        # Arbeitnow marca remote boolean -> garante modalidade
        if raw.raw_payload.get("remote") and not modality:
            modality = "remoto"
        fp = build_fingerprint(company, title, loc, raw.url, desc)
        return NormalizedJob(
            title=title,
            company_name=company,
            url=raw.url,
            description=desc,
            location=loc,
            modality=modality,
            seniority=seniority,
            technologies=techs,
            raw_payload=raw.raw_payload,
            fingerprint=fp,
        )
