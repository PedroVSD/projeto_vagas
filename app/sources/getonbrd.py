"""Fonte Get on Board - vagas de tecnologia na América Latina.

API pública: https://www.getonbrd.com/api/v0
- Cobre Chile, Argentina e demais países LATAM, além de vagas remotas.
- Sem auth e sem scraping; usa o endpoint público de vagas por categoria.
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

API_URL = "https://www.getonbrd.com/api/v0/categories/programming/jobs"
DEFAULT_PAGES = 2
PER_PAGE = 100


class GetOnBoardSource(JobSource):
    name = "getonbrd"

    def __init__(self, timeout: int = 20, pages: int = DEFAULT_PAGES):
        self.timeout = timeout
        self.pages = pages

    def fetch_jobs(self) -> list[RawJob]:
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for page in range(1, self.pages + 1):
                try:
                    r = client.get(
                        API_URL,
                        params={
                            "per_page": PER_PAGE,
                            "page": page,
                            "expand[]": ["company", "seniority"],
                        },
                        headers={"Accept": "application/json", "User-Agent": "job-finder/0.1"},
                    )
                    r.raise_for_status()
                    jobs = r.json().get("data") or []
                except Exception as e:
                    logger.warning("GetOnBoard fetch falhou page=%s: %s", page, e)
                    break

                if not jobs:
                    break

                for job in jobs:
                    attrs = job.get("attributes") or {}
                    url = (job.get("links") or {}).get("public_url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    company = (
                        ((attrs.get("company") or {}).get("data") or {}).get("attributes") or {}
                    ).get("name") or "Desconhecida"
                    location = ", ".join(attrs.get("countries") or []) or attrs.get("remote_zone")
                    all_raws.append(
                        RawJob(
                            external_id=str(job.get("id") or url),
                            title=str(attrs.get("title") or "Sem título"),
                            company_name=str(company),
                            url=str(url),
                            description=attrs.get("description"),
                            location=location,
                            raw_payload=attrs,
                        )
                    )

                if len(jobs) < PER_PAGE:
                    break
                time.sleep(1.0)

        logger.info("GetOnBoard fetch: %d vagas", len(all_raws))
        return all_raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location)
        payload = raw.raw_payload or {}

        techs = extract_technologies(f"{title} {desc or ''}")
        seniority = extract_seniority(title, desc)
        if seniority is None:
            seniority_key = (
                ((payload.get("seniority") or {}).get("data") or {}).get("attributes") or {}
            ).get("locale_key")
            seniority = {
                "intern": "intern",
                "junior": "junior",
                "semi_senior": "pleno",
                "senior": "senior",
                "staff": "staff",
            }.get(str(seniority_key or "").lower())

        modality = extract_modality(loc, desc)
        if modality is None:
            if payload.get("remote"):
                modality = "remoto"
            elif "hybrid" in str(payload.get("remote_modality") or "").lower():
                modality = "hibrido"
            else:
                modality = "presencial"

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
