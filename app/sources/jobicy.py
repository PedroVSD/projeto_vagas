"""Fonte Jobicy - API pública de vagas remotas por país.

API: https://jobicy.com/api/v2/remote-jobs
- Uso gratuito com atribuição ao Jobicy (a URL original da vaga é preservada).
- Permite filtrar por geo (país), alinhado ao perfil atual.
- Sem auth, sem scraping e com rate-limit entre requisições.
"""

from __future__ import annotations

import logging
import time

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

API_URL = "https://jobicy.com/api/v2/remote-jobs"
DEFAULT_GEOS = ["chile", "argentina", "spain", "portugal", "poland", "usa", "canada"]


class JobicySource(JobSource):
    name = "jobicy"

    def __init__(
        self,
        geos: list[str] | None = None,
        count: int = 50,
        timeout: int = 20,
    ):
        self.geos = geos or DEFAULT_GEOS
        self.count = count
        self.timeout = timeout

    def fetch_jobs(self) -> list[RawJob]:
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for geo in self.geos:
                try:
                    r = client.get(
                        API_URL,
                        params={"count": self.count, "geo": geo},
                        headers={"Accept": "application/json", "User-Agent": "job-finder/0.1"},
                    )
                    r.raise_for_status()
                    jobs = r.json().get("jobs") or []
                except Exception as e:
                    logger.warning("Jobicy fetch falhou geo=%s: %s", geo, e)
                    continue

                for j in jobs:
                    url = j.get("url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    title = j.get("jobTitle") or "Sem título"
                    description = j.get("jobDescription") or j.get("jobExcerpt")
                    all_raws.append(
                        RawJob(
                            external_id=str(j.get("id") or url),
                            title=str(title),
                            company_name=str(j.get("companyName") or "Desconhecida"),
                            url=str(url),
                            description=description,
                            location=j.get("jobGeo") or geo.title(),
                            raw_payload=j,
                        )
                    )
                time.sleep(1.0)

        logger.info("Jobicy fetch: %d vagas (geos=%s)", len(all_raws), ",".join(self.geos))
        return all_raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location)
        hay = f"{title} {desc or ''} {loc or ''}"
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
            raw_payload=raw.raw_payload,
            fingerprint=fp,
        )
