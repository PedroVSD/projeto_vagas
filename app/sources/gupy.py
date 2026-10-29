"""Fonte Gupy - maior ATS brasileiro (estágio/júnior).

Site: https://portal.gupy.io  (https://www.gupy.io)
- Sem API pública documentada estável; usa endpoints públicos do portal
  (mesmo que candidatos veem sem login) + fallback HTML.
- Endpoints tentados:
  1. https://portal.gupy.io/api/v1/jobs/search (POST/GET com filtros)
  2. https://api.gupy.io/api/v1/jobs (legado)
  3. Scraping https://portal.gupy.io/job-search/term=<query>
- Respeita ToS: GET/POST público, sem auth, User-Agent identificável,
  rate-limit 1.5s, retorna [] em 403/429/404 sem quebrar pipeline.
- Perfil alvo: Estágio/Júnior Python/Dados/MLOps - usa queries do YAML
  filtradas por estágio/júnior quando possível (type=internship).
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1 (+https://github.com/job-finder)",
    "Accept": "text/html,application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

API_CANDIDATES = [
    "https://portal.gupy.io/api/v1/jobs",
    "https://api.gupy.io/api/v1/jobs",
]
SEARCH_HTML = "https://portal.gupy.io/job-search/term={term}"


class GupySource(JobSource):
    """Adapter Gupy - ATS brasileiro líder."""

    name = "gupy"

    def __init__(self, timeout: int = 15, max_per_query: int = 8, max_queries: int = 4):
        self.timeout = timeout
        self.max_per_query = max_per_query
        self.max_queries = max_queries

    def _get_queries(self) -> list[str]:
        try:
            from app.services.query_service import get_all_queries

            qs = get_all_queries()
            preferred = []
            for q in qs:
                txt = q.get("query", "")
                low = txt.lower()
                if any(
                    k in low
                    for k in [
                        "junior",
                        "pleno",
                        "golang",
                        "go developer",
                        "go engineer",
                        "python",
                        "data engineer",
                        "data scientist",
                        "mlops",
                        "software",
                    ]
                ):
                    preferred.append(txt)
            return (preferred or [q["query"] for q in qs])[: self.max_queries]
        except Exception:
            return [
                "junior python",
                "pleno data engineer",
                "junior golang",
                "pleno backend",
            ][: self.max_queries]

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
                time.sleep(1.5)
            except Exception as e:
                logger.warning("Gupy fetch falhou query='%s': %s", q, e)
                continue
        logger.info("Gupy fetch: %d vagas (queries=%d)", len(all_raws), len(queries))
        return all_raws

    def _fetch_query(self, query: str) -> list[RawJob]:
        # 1. tenta API JSON primeiro (mais estável quando disponível)
        for api_url in API_CANDIDATES:
            try:
                raws = self._fetch_api(api_url, query)
                if raws:
                    return raws[: self.max_per_query]
            except Exception as e:
                logger.debug("Gupy API %s falhou query='%s': %s", api_url, query, e)
                continue
        # 2. fallback HTML search
        try:
            return self._fetch_html(query)[: self.max_per_query]
        except Exception as e:
            logger.debug("Gupy HTML falhou query='%s': %s", query, e)
            return []

    def _fetch_api(self, base: str, query: str) -> list[RawJob]:
        # Gupy API espera filtros via query params; tentamos variações
        params_variants = [
            {"searchTerm": query, "limit": self.max_per_query, "offset": 0},
            {"q": query, "limit": self.max_per_query},
            {"term": query, "limit": self.max_per_query},
        ]
        for params in params_variants:
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
                    r = c.get(base, params=params)
                    if r.status_code in (403, 404, 429):
                        continue
                    r.raise_for_status()
                    data = r.json()
                    items = None
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = (
                            data.get("data")
                            or data.get("jobs")
                            or data.get("results")
                            or data.get("items")
                        )
                    if not isinstance(items, list) or not items:
                        continue
                    raws: list[RawJob] = []
                    for j in items[: self.max_per_query]:
                        if not isinstance(j, dict):
                            continue
                        title = j.get("title") or j.get("name") or query
                        company = j.get("company") or j.get("companyName") or j.get("organization")
                        if isinstance(company, dict):
                            company = company.get("name") or "Gupy"
                        company = company or "Gupy"
                        url = (
                            j.get("url")
                            or j.get("jobUrl")
                            or j.get("link")
                            or f"https://portal.gupy.io/jobs/{j.get('id','')}"
                        )
                        desc = j.get("description") or j.get("about") or title
                        loc = j.get("location") or j.get("workplace") or j.get("city") or "Brasil"
                        raws.append(
                            RawJob(
                                external_id=f"gupy-{j.get('id') or url}",
                                title=str(title),
                                company_name=str(company),
                                url=str(url),
                                description=str(desc)[:3000] if desc else None,
                                location=str(loc) if loc else None,
                                raw_payload=j,
                            )
                        )
                    if raws:
                        return raws
            except Exception:
                continue
        return []

    def _fetch_html(self, query: str) -> list[RawJob]:
        slug = urllib.parse.quote(query.lower().strip())
        url = SEARCH_HTML.format(term=slug)
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
            r = c.get(url)
            if r.status_code in (403, 404, 429):
                return []
            r.raise_for_status()
            html = r.text
        if not html or "gupy" not in html.lower():
            return []
        soup = BeautifulSoup(html, "lxml")
        # Gupy renderiza cards com data-testid ou links /job/
        links = soup.select('a[href*="/job/"], a[href*="/jobs/"], a[data-testid*="job"]')
        if not links:
            links = [a for a in soup.select("a[href]") if "vaga" in a.get_text().lower() or "estágio" in a.get_text().lower()]
        raws: list[RawJob] = []
        seen: set[str] = set()
        for a in links:
            href = a.get("href", "").split("?")[0].strip()
            if not href or href in seen:
                continue
            if href.startswith("/"):
                href = f"https://portal.gupy.io{href}"
            if "gupy.io" not in href:
                continue
            seen.add(href)
            container = a.find_parent(["div", "article", "li", "section"])
            title = a.get_text(strip=True)
            if container:
                h = container.select_one("h2, h3, h4, p")
                if h and len(h.get_text(strip=True)) > 6:
                    title = h.get_text(strip=True)
            if not title or len(title) < 6 or title.lower() in ("candidatar-se", "ver vaga", "saiba mais"):
                continue
            company = "Gupy"
            location = "Brasil"
            desc = None
            if container:
                txt = container.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                for p in parts[:3]:
                    if p != title and len(p) < 70 and "gupy" not in p.lower():
                        company = p
                        break
                for p in parts:
                    low = p.lower()
                    if any(k in low for k in ["brasil", "remoto", "híbrido", "hibrido", "são paulo", "rio de janeiro", "remota"]):
                        location = p
                        break
                desc = txt[:2500]
            m = re.search(r"/job/([^/]+)", href)
            ext = m.group(1) if m else href
            raws.append(
                RawJob(
                    external_id=f"gupy-{ext}",
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
        seniority = extract_seniority(title, desc) or "intern"
        modality = extract_modality(loc, desc) or "hibrido"
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
