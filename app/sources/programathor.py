"""Fonte Programathor - vagas de tecnologia BR.

Site: https://programathor.com.br/jobs
- Agregador focado em tecnologia, muitas vagas Júnior/Python.
- Sem API pública; scraping HTML público com paginação.
- Respeita ToS: GET público, User-Agent, 1 req/s, retorna [] em erro.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from app.services.deduplication import build_fingerprint
from app.services.normalization import (
    extract_modality,
    extract_seniority,
    extract_technologies,
    normalize_text,
)
from app.sources.base import JobSource, NormalizedJob, RawJob

logger = logging.getLogger(__name__)

BASE_URL = "https://programathor.com.br"
SEARCH_URL = "https://programathor.com.br/jobs/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class ProgramathorSource(JobSource):
    """Adapter Programathor - tech BR."""

    name = "programathor"

    def __init__(self, timeout: int = 15, max_per_query: int = 8, max_queries: int = 4):
        self.timeout = timeout
        self.max_per_query = max_per_query
        self.max_queries = max_queries

    def _get_queries(self) -> list[str]:
        try:
            from app.services.query_service import get_all_queries

            qs = get_all_queries()
            preferred: list[str] = []
            for q in qs:
                txt = q.get("query", "")
                low = txt.lower()
                if any(k in low for k in ["python", "data engineer", "junior", "estagio", "estágio", "backend", "mlops"]):
                    preferred.append(txt)
            return (preferred or [q["query"] for q in qs])[: self.max_queries]
        except Exception:
            return ["python junior", "data engineer", "estagio python", "backend junior"][: self.max_queries]

    def fetch_jobs(self) -> list[RawJob]:
        queries = self._get_queries()
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        for q in queries:
            try:
                raws = self._fetch_query(q)
                for r in raws:
                    if r.url not in seen:
                        seen.add(r.url)
                        all_raws.append(r)
                time.sleep(1.0)
            except Exception as e:
                logger.warning("Programathor fetch falhou query='%s': %s", q, e)
                continue
        logger.info("Programathor fetch: %d vagas (queries=%d)", len(all_raws), len(queries))
        return all_raws

    def _fetch_query(self, query: str) -> list[RawJob]:
        params = {"q": query}
        url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
                r = c.get(url)
                if r.status_code in (403, 404, 429):
                    return []
                r.raise_for_status()
                html = r.text
        except Exception as e:
            logger.debug("Programathor request erro query='%s': %s", query, e)
            return []
        # fallback: página principal se search não existir
        if not html or ("vaga" not in html.lower() and "job" not in html.lower()):
            # tenta home + filtro
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
                    r = c.get(f"{BASE_URL}/jobs", params={"search": query})
                    if r.status_code not in (403, 404):
                        r.raise_for_status()
                        html = r.text
            except Exception:
                return []
        if not html:
            return []
        return self._parse_html(html, query)

    def _parse_html(self, html: str, query: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "lxml")
        links = soup.select('a[href*="/jobs/"], a[href*="/job/"], a[href*="/vaga"]')
        if not links:
            links = [a for a in soup.select("a[href]") if any(k in a.get_text().lower() for k in ["python", "junior", "estágio", "dados", "data"])]
        raws: list[RawJob] = []
        seen: set[str] = set()
        for a in links:
            href = a.get("href", "").split("?")[0].strip()
            if not href or href in seen:
                continue
            if href.startswith("/"):
                href = f"{BASE_URL}{href}"
            if "programathor.com.br" not in href:
                continue
            seen.add(href)
            container = a.find_parent(["div", "article", "li", "tr"])
            title = a.get_text(strip=True)
            if container:
                h = container.select_one("h2, h3, h4, .title, .job-title")
                if h and len(h.get_text(strip=True)) > 5:
                    title = h.get_text(strip=True)
            if not title or len(title) < 5 or title.lower() in ("ver vaga", "candidatar-se", "saiba mais"):
                continue
            company = "Programathor"
            location = "Brasil"
            desc = None
            if container:
                txt = container.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                for p in parts[:3]:
                    if p != title and len(p) < 70:
                        low = p.lower()
                        if not any(k in low for k in ["candidatar", "ver vaga"]):
                            company = p
                            break
                for p in parts:
                    low = p.lower()
                    if any(k in low for k in ["remoto", "presencial", "híbrido", "hibrido", "são paulo", "rio de janeiro", "brasil"]):
                        location = p
                        break
                desc = txt[:2500]
            m = re.search(r"/jobs/([^/]+)", href)
            ext = m.group(1) if m else href
            raws.append(
                RawJob(
                    external_id=f"programathor-{ext}",
                    title=title,
                    company_name=company,
                    url=href,
                    description=desc or title,
                    location=location,
                    raw_payload={"href": href, "query": query},
                )
            )
            if len(raws) >= self.max_per_query:
                break
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        loc = normalize_text(raw.location) or "Brasil"
        desc = raw.description
        full = f"{title} {desc or ''} {loc or ''}"
        techs = extract_technologies(full)
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
