"""Fonte Vagas.com.br - scraping HTML respeitoso.

Site: https://www.vagas.com.br/vagas-de-{termo}
- Sem API pública; usa HTML público com paginação.
- Respeita ToS/robots: apenas GET público, User-Agent identificável,
  sem bypass de login/CAPTCHA, rate-limit 1 req/s, retorna [] em erro.
- Perfil alvo: Estágio/Júnior em Python, Dados, MLOps -> queries do
  config/search_queries.yaml mapeadas para slug "vagas-de-<termo>".

Ex: "Junior Data Engineer" -> https://www.vagas.com.br/vagas-de-junior-data-engineer
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

BASE_URL = "https://www.vagas.com.br"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1 (+https://github.com/job-finder)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def _query_to_slug(query: str) -> str:
    # "Junior Data Engineer" -> "junior-data-engineer"
    slug = query.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return urllib.parse.quote(slug)


class VagasSource(JobSource):
    """Adapter Vagas.com - HTML scraping leve."""

    name = "vagas"

    def __init__(self, timeout: int = 15, max_per_query: int = 8, max_queries: int = 4):
        self.timeout = timeout
        self.max_per_query = max_per_query
        self.max_queries = max_queries

    def _get_queries(self) -> list[str]:
        try:
            from app.services.query_service import get_all_queries

            qs = get_all_queries()
            # seleciona queries mais aderentes ao perfil Júnior/Pleno + python/dados/Golang
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
                        "desenvolvedor",
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
                raws = self._fetch_for_slug(_query_to_slug(q), q)
                for r in raws:
                    if r.url not in seen:
                        seen.add(r.url)
                        all_raws.append(r)
                time.sleep(1.0)  # respeita rate limit
            except Exception as e:
                logger.warning("Vagas fetch falhou query='%s': %s", q, e)
                continue

        logger.info("Vagas fetch: %d vagas (queries=%d)", len(all_raws), len(queries))
        return all_raws

    def _fetch_for_slug(self, slug: str, original_query: str) -> list[RawJob]:
        url = f"{BASE_URL}/vagas-de-{slug}"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
                r = c.get(url)
                if r.status_code in (403, 404, 429):
                    logger.debug("Vagas status %s slug=%s", r.status_code, slug)
                    return []
                r.raise_for_status()
                html = r.text
        except Exception as e:
            logger.warning("Vagas request erro slug=%s: %s", slug, e)
            return []

        if not html or "/vagas/v" not in html:
            logger.debug("Vagas sem resultados slug=%s", slug)
            return []

        return self._parse_html(html, original_query)

    def _parse_html(self, html: str, query: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "lxml")
        # links de vagas: href="/vagas/v123456/..."
        links = soup.select('a[href*="/vagas/v"]')
        raws: list[RawJob] = []
        seen_href: set[str] = set()

        for a in links:
            href = a.get("href", "").split("?")[0]
            if not href or href in seen_href:
                continue
            if not re.search(r"/vagas/v\d+", href):
                continue
            seen_href.add(href)
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"

            # tenta extrair título do link ou do h2/h3 pai
            title = a.get_text(strip=True)
            # sobe até encontrar container com infos
            container = a.find_parent(["li", "div", "article"])
            if container:
                # título mais preciso em h2/h3
                h = container.select_one("h2, h3")
                if h and h.get_text(strip=True):
                    title = h.get_text(strip=True)
                # empresa: texto próximo, geralmente após título
                # Vagas.com mostra empresa em <span> ou div com nível
            if not title or len(title) < 3:
                title = query

            # empresa e nível: procura no container
            company = "Confidencial"
            location = None
            level = None
            desc = None
            if container:
                text = container.get_text(separator=" | ", strip=True)
                # heurísticas simples
                # Ex: "Dev | Confidencial | Júnior/Trainee | Desc... | BH / MG"
                parts = [p.strip() for p in text.split("|") if p.strip()]
                # empresa geralmente segunda parte se não for nível
                for p in parts[:4]:
                    low = p.lower()
                    if any(
                        k in low
                        for k in ["júnior", "trainee", "estágio", "pleno", "sênior", "assistente"]
                    ):
                        level = p
                    elif "/" in p and any(
                        c in p for c in ["MG", "SP", "RJ", "RS", "PR", "BA", "DF", "Brasil"]
                    ):
                        location = p
                    elif p != title and len(p) < 80 and not company or company == "Confidencial":
                        # heurística fraca mas melhora sobre "Confidencial"
                        if p not in (level or "") and p not in (location or ""):
                            company = p
                desc = " | ".join(parts[2:5])[:2000] if len(parts) > 2 else text[:2000]

            # extrai tecnologias do título+desc para já preencher
            raws.append(
                RawJob(
                    external_id=f"vagas-{href.split('/')[-1]}",
                    title=title,
                    company_name=company,
                    url=full_url,
                    description=desc or title,
                    location=location,
                    raw_payload={"query": query, "href": href, "level": level},
                )
            )
            if len(raws) >= self.max_per_query:
                break
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        loc = normalize_text(raw.location)
        desc = raw.description
        full = f"{title} {desc or ''} {loc or ''}"
        techs = extract_technologies(full)
        seniority = extract_seniority(title, desc or raw.raw_payload.get("level"))
        modality = extract_modality(loc, desc)
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
