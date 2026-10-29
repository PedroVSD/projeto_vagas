"""Fonte Remote OK - API pública de vagas remotas globais.

API: https://remoteok.com/api
- Uso gratuito; os termos da API pedem atribuição e link de volta para a vaga.
- A URL original é preservada e enviada nas notificações.
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

API_URL = "https://remoteok.com/api"


class RemoteOkSource(JobSource):
    name = "remoteok"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                r = client.get(
                    API_URL,
                    headers={"Accept": "application/json", "User-Agent": "job-finder/0.1"},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning("RemoteOK fetch falhou: %s", e)
            return []

        if not isinstance(data, list):
            logger.warning("RemoteOK formato inesperado: %s", type(data))
            return []

        raws: list[RawJob] = []
        seen: set[str] = set()
        for j in data:
            if not isinstance(j, dict) or not j.get("position") or not j.get("id"):
                continue
            url = j.get("url") or j.get("apply_url")
            if not url or url in seen:
                continue
            seen.add(url)
            raws.append(
                RawJob(
                    external_id=str(j.get("id")),
                    title=str(j.get("position")),
                    company_name=str(j.get("company") or "Desconhecida"),
                    url=str(url),
                    description=j.get("description"),
                    location=j.get("location") or "Remote",
                    raw_payload=j,
                )
            )

        logger.info("RemoteOK fetch: %d vagas", len(raws))
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location) or "Remote"
        payload = raw.raw_payload or {}
        tags = payload.get("tags") or []
        hay = f"{title} {desc or ''} {' '.join(tags)} {loc}"
        techs = extract_technologies(hay)
        seniority = extract_seniority(title, desc)
        modality = extract_modality(loc, desc) or "remoto"
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
            raw_payload=payload,
            fingerprint=fp,
        )
