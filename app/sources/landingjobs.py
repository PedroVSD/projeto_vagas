"""Fonte Landing.jobs - vagas de tecnologia em Portugal e Europa.

API pública: https://landing.jobs/api/v1/jobs
- Cobre vagas remotas, híbridas e presenciais em Portugal/Europa.
- Sem auth e sem scraping; consome a API pública do portal.
"""

from __future__ import annotations

import logging
import time
import urllib.parse

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

API_URL = "https://landing.jobs/api/v1/jobs"
DEFAULT_QUERIES = [
    {"remote": "true", "limit": 100},
    {"countries": "PT", "limit": 100},
]


class LandingJobsSource(JobSource):
    name = "landingjobs"

    def __init__(self, timeout: int = 20, queries: list[dict] | None = None):
        self.timeout = timeout
        self.queries = queries or DEFAULT_QUERIES

    def fetch_jobs(self) -> list[RawJob]:
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for params in self.queries:
                try:
                    r = client.get(
                        API_URL,
                        params=params,
                        headers={"Accept": "application/json", "User-Agent": "job-finder/0.1"},
                    )
                    r.raise_for_status()
                    jobs = r.json()
                except Exception as e:
                    logger.warning("Landing.jobs fetch falhou params=%s: %s", params, e)
                    continue

                if not isinstance(jobs, list):
                    continue

                for j in jobs:
                    url = j.get("url")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    all_raws.append(
                        RawJob(
                            external_id=str(j.get("id") or url),
                            title=str(j.get("title") or "Sem título"),
                            company_name=self._company_from_url(str(url)),
                            url=str(url),
                            description=self._build_description(j),
                            location=self._location(j),
                            raw_payload=j,
                        )
                    )
                time.sleep(1.0)

        logger.info("Landing.jobs fetch: %d vagas", len(all_raws))
        return all_raws

    @staticmethod
    def _company_from_url(url: str) -> str:
        parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "at":
            return parts[1].replace("-", " ").title()
        return "Landing.jobs"

    @staticmethod
    def _location(job: dict) -> str:
        locations = job.get("locations") or []
        if isinstance(locations, list) and locations:
            first = locations[0] or {}
            city = first.get("city")
            country = first.get("country_code")
            label = ", ".join(v for v in (city, country) if v)
            if label:
                return f"{label} (Remote)" if job.get("remote") else label
        return "Remote" if job.get("remote") else "Portugal"

    @staticmethod
    def _build_description(job: dict) -> str:
        parts = [
            job.get("role_description"),
            job.get("main_requirements"),
            job.get("nice_to_have"),
            job.get("perks"),
        ]
        return " ".join(str(p) for p in parts if p)

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location)
        payload = raw.raw_payload or {}
        tags = payload.get("tags") or []

        techs = extract_technologies(f"{title} {desc or ''} {' '.join(tags)}")
        seniority = extract_seniority(title, desc)
        modality = "remoto" if payload.get("remote") else extract_modality(loc, desc)
        if modality is None:
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
