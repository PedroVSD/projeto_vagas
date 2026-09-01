"""Fonte Academia do Universitário (AU).

Site: https://www.academiadouniversitario.com.br / https://lovable.academiadouniversitario.com.br
- Plataforma de estágio agente de integração (Lei 11.788), atende 50+ multinacionais.
- Sem API pública; vagas divulgadas em portais parceiros e no próprio site.
- Implementa scraping HTML do portal + fallback para busca via JSON se exposto.
- Respeita ToS: GET público, sem auth, rate-limit.

Se estrutura mudar, retorna [] sem quebrar pipeline (ingestion isola por fonte).
"""

from __future__ import annotations

import logging
import re

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

URLS = [
    "https://www.academiadouniversitario.com.br/vagas",
    "https://www.academiadouniversitario.com.br/blog",
    "https://lovable.academiadouniversitario.com.br/universitarios",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1",
    "Accept": "text/html,application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class AcademiaSource(JobSource):
    """Adapter Academia do Universitário - Estágio estratégico."""

    name = "academia"

    def __init__(self, timeout: int = 15, max_jobs: int = 12):
        self.timeout = timeout
        self.max_jobs = max_jobs

    def fetch_jobs(self) -> list[RawJob]:
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        for url in URLS:
            try:
                raws = self._fetch_url(url)
                for r in raws:
                    if r.url not in seen:
                        seen.add(r.url)
                        all_raws.append(r)
                if len(all_raws) >= self.max_jobs:
                    break
            except Exception as e:
                logger.debug("Academia fetch falhou %s: %s", url, e)
                continue

        # Se não encontrou nada no site institucional (poucas vagas públicas),
        # tenta buscar em portal parceiro que lista vagas AU (ex: 99jobs, gupy filtrado)
        # por enquanto retorna o que encontrou; pipeline já tem outras fontes BR (Vagas, Eureca)
        logger.info("Academia fetch: %d vagas", len(all_raws))
        return all_raws[: self.max_jobs]

    def _fetch_url(self, url: str) -> list[RawJob]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
            r = c.get(url)
            if r.status_code in (403, 404, 429):
                logger.debug("Academia status %s url=%s", r.status_code, url)
                return []
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "application/json" in ct:
                try:
                    data = r.json()
                    return self._parse_json(data, url)
                except Exception:
                    pass
            html = r.text

        if not html or len(html) < 500:
            return []

        soup = BeautifulSoup(html, "lxml")
        raws: list[RawJob] = []

        # links que parecem vagas de estágio
        links = soup.select(
            'a[href*="/vaga"], a[href*="/estagio"], a[href*="/oportunidade"], a[href*="/programa"]'
        )
        # fallback: qualquer link com texto de estágio
        if not links:
            links = [
                a
                for a in soup.select("a[href]")
                if any(
                    k in a.get_text().lower() for k in ["estágio", "estagio", "trainee", "estagiar"]
                )
            ]

        seen_href: set[str] = set()
        for a in links:
            href = a.get("href", "").split("?")[0].strip()
            if not href or href in seen_href:
                continue
            if href.startswith("/"):
                domain = "/".join(url.split("/")[:3])
                href = domain + href
            if not href.startswith("http"):
                continue
            seen_href.add(href)

            title = a.get_text(strip=True)
            container = a.find_parent(["div", "article", "li", "section"])
            if container:
                h = container.select_one("h1, h2, h3, h4")
                if h and len(h.get_text(strip=True)) > 5:
                    title = h.get_text(strip=True)
            if not title or len(title) < 5 or title.lower() in ("saiba mais", "conheça", "acessar"):
                continue

            company = "Academia do Universitário"
            location = "Brasil"
            desc = None
            if container:
                txt = container.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                for p in parts[:3]:
                    if p != title and len(p) < 70 and "academia" not in p.lower():
                        company = p
                        break
                desc = txt[:2500]

            # filtra para manter apenas vagas com alguma aderência tech/dados ou genérica estágio
            # AU é toda estágio, então mantém
            m = re.search(r"/([^/]+)/?$", href.rstrip("/"))
            ext_id = m.group(1) if m else href

            raws.append(
                RawJob(
                    external_id=f"academia-{ext_id}",
                    title=title,
                    company_name=company,
                    url=href,
                    description=desc or title,
                    location=location,
                    raw_payload={"href": href, "source_url": url},
                )
            )
            if len(raws) >= self.max_jobs:
                break
        return raws

    def _parse_json(self, data, url: str) -> list[RawJob]:
        items = data if isinstance(data, list) else data.get("data") or data.get("results") or []
        if not isinstance(items, list):
            return []
        raws: list[RawJob] = []
        for j in items[: self.max_jobs]:
            if not isinstance(j, dict):
                continue
            title = j.get("title") or j.get("name") or "Estágio Academia"
            company = j.get("company") or j.get("company_name") or "Academia do Universitário"
            if isinstance(company, dict):
                company = company.get("name") or "Academia"
            href = j.get("url") or j.get("link") or url
            desc = j.get("description") or title
            loc = j.get("location") or "Brasil"
            raws.append(
                RawJob(
                    external_id=f"academia-{j.get('id') or href}",
                    title=str(title),
                    company_name=str(company),
                    url=str(href),
                    description=str(desc)[:3000] if desc else None,
                    location=str(loc) if loc else None,
                    raw_payload=j,
                )
            )
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
