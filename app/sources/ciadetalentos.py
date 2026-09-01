"""Fonte Companhia de Estágios / Cia de Talentos.

Sites:
  - https://www.ciadeestagios.com.br/vagas-de-estagio/
  - https://www.ciadetalentos.com.br/vagas (quando aplicável)

Foco: Estágio, Trainee, Jovem Aprendiz - 100% aderente ao perfil Júnior/Estágio.
Sem API pública; scraping HTML público, respeita ToS (GET público, sem auth, rate-limit).
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
    "https://www.ciadeestagios.com.br/vagas-de-estagio/",
    "https://www.ciadetalentos.com.br/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class CiaDeTalentosSource(JobSource):
    """Adapter Cia de Talentos / Companhia de Estágios."""

    name = "ciadetalentos"

    def __init__(self, timeout: int = 15, max_jobs: int = 15):
        self.timeout = timeout
        self.max_jobs = max_jobs

    def fetch_jobs(self) -> list[RawJob]:
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        for base_url in URLS:
            try:
                raws = self._fetch_url(base_url)
                for r in raws:
                    if r.url not in seen:
                        seen.add(r.url)
                        all_raws.append(r)
                if len(all_raws) >= self.max_jobs:
                    break
            except Exception as e:
                logger.warning("CiaDeTalentos fetch falhou %s: %s", base_url, e)
                continue
        logger.info("CiaDeTalentos fetch: %d vagas", len(all_raws))
        return all_raws[: self.max_jobs]

    def _fetch_url(self, url: str) -> list[RawJob]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
            r = c.get(url)
            if r.status_code in (403, 404, 429):
                logger.debug("CiaDeTalentos status %s url=%s", r.status_code, url)
                return []
            r.raise_for_status()
            html = r.text

        if not html or "estágio" not in html.lower() and "estagio" not in html.lower():
            logger.debug("CiaDeTalentos HTML sem estágio url=%s", url)
            return []

        soup = BeautifulSoup(html, "lxml")
        raws: list[RawJob] = []

        # links para vagas: padrão /vaga/, /programa/, /oportunidade/, ou cards
        links = soup.select(
            'a[href*="/vaga"], a[href*="/programa"], a[href*="/estagio"], a[href*="/oportunidade"]'
        )
        if not links:
            # fallback: todos links que parecem vaga (contêm "estágio" no texto)
            links = [
                a
                for a in soup.select("a[href]")
                if "estag" in a.get_text().lower() or "trainee" in a.get_text().lower()
            ]

        seen_href: set[str] = set()
        for a in links:
            href = a.get("href", "").split("?")[0].strip()
            if not href or href in seen_href:
                continue
            if href.startswith("/"):
                # resolve relativo ao domínio base
                domain = "/".join(url.split("/")[:3])
                href = domain + href
            if not href.startswith("http"):
                continue
            seen_href.add(href)

            # título
            title = a.get_text(strip=True)
            container = a.find_parent(["div", "article", "li"])
            if container:
                h = container.select_one("h2, h3, h4")
                if h and len(h.get_text(strip=True)) > 5:
                    title = h.get_text(strip=True)
            if (
                not title
                or len(title) < 5
                or title.lower() in ("saiba mais", "inscreva-se", "ver vagas")
            ):
                continue

            # filtros de relevância para perfil Tech/Dados
            # mantém tudo mas prioriza tech se contiver keywords, senão ainda guarda (estágio geral)
            company = "Cia de Talentos"
            location = "Brasil"
            desc = None
            if container:
                txt = container.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                for p in parts[:3]:
                    if p != title and len(p) < 60:
                        company = p
                        break
                for p in parts:
                    if any(
                        k in p.lower()
                        for k in [
                            "brasil",
                            "remoto",
                            "híbrido",
                            "são paulo",
                            "rio de janeiro",
                            "belo horizonte",
                        ]
                    ):
                        location = p
                        break
                desc = txt[:2500]

            # extrai id
            m = re.search(r"/([^/]+)/?$", href.rstrip("/"))
            ext_id = m.group(1) if m else href

            raws.append(
                RawJob(
                    external_id=f"ciadetalentos-{ext_id}",
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
