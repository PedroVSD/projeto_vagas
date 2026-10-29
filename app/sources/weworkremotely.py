"""Fonte We Work Remotely - feed RSS público de vagas remotas.

Feed: https://weworkremotely.com/categories/remote-programming-jobs.rss
- Sem auth e sem scraping; consome o RSS oficial.
- Vagas 100% remotas, com região e descrição.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import httpx

from app.services.deduplication import build_fingerprint
from app.services.normalization import (
    extract_seniority,
    extract_technologies,
    normalize_text,
)
from app.sources.base import JobSource, NormalizedJob, RawJob

logger = logging.getLogger(__name__)

FEED_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"


class WeWorkRemotelySource(JobSource):
    name = "weworkremotely"

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def fetch_jobs(self) -> list[RawJob]:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                r = client.get(
                    FEED_URL,
                    headers={
                        "Accept": "application/rss+xml",
                        "User-Agent": "job-finder/0.1",
                    },
                )
                r.raise_for_status()
                root = ET.fromstring(r.text)
        except Exception as e:
            logger.warning("WeWorkRemotely fetch falhou: %s", e)
            return []

        raws: list[RawJob] = []
        seen: set[str] = set()
        for item in root.findall("./channel/item"):
            title_full = (item.findtext("title") or "Sem título").strip()
            url = (item.findtext("link") or item.findtext("guid") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)

            company = "We Work Remotely"
            title = title_full
            if ": " in title_full:
                company, title = title_full.split(": ", 1)

            raws.append(
                RawJob(
                    external_id=(item.findtext("guid") or url).strip(),
                    title=title.strip(),
                    company_name=company.strip(),
                    url=url,
                    description=item.findtext("description"),
                    location=(item.findtext("region") or "Remote").strip(),
                    raw_payload={
                        "category": item.findtext("category"),
                        "pubDate": item.findtext("pubDate"),
                        "region": item.findtext("region"),
                    },
                )
            )

        logger.info("WeWorkRemotely fetch: %d vagas", len(raws))
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location) or "Remote"
        techs = extract_technologies(f"{title} {desc or ''} {loc}")
        seniority = extract_seniority(title, desc)
        fp = build_fingerprint(company, title, loc, raw.url, desc)
        return NormalizedJob(
            title=title,
            company_name=company,
            url=raw.url,
            description=desc,
            location=loc,
            modality="remoto",
            seniority=seniority,
            technologies=techs,
            raw_payload=raw.raw_payload,
            fingerprint=fp,
        )
