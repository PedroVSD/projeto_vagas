"""Fonte Eureca (eureca.me) - vagas de estágio/trainee.

Site: https://app.eureca.me/search?career_type=internship
- Plataforma brasileira focada em Estágio/Trainee, muito aderente ao perfil.
- Sem API pública documentada; consome HTML/JSON público do portal.
- Implementa fetch HTML com fallback para tentativa de API JSON se exposta.
- Respeita ToS: GET público, sem auth, rate-limit, retorna [] em erro.

Se a estrutura HTML mudar, o scraper continua resiliente (retorna [] sem quebrar pipeline).
"""

from __future__ import annotations

import logging
import re
import time

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

SEARCH_URL = "https://app.eureca.me/search"
API_CANDIDATES = [
    "https://app.eureca.me/api/opportunities",
    "https://app.eureca.me/api/search",
    "https://api.eureca.me/opportunities",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1",
    "Accept": "text/html,application/json",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class EurecaSource(JobSource):
    """Adapter Eureca - Estágio/Trainee Brasil."""

    name = "eureca"

    def __init__(self, timeout: int = 15, max_jobs: int = 15):
        self.timeout = timeout
        self.max_jobs = max_jobs

    def fetch_jobs(self) -> list[RawJob]:
        # 1. tenta API JSON primeiro (mais estável se existir)
        for api_url in API_CANDIDATES:
            try:
                raws = self._fetch_api(api_url)
                if raws:
                    logger.info("Eureca fetch via API %s: %d vagas", api_url, len(raws))
                    return raws[: self.max_jobs]
            except Exception as e:
                logger.debug("Eureca API %s falhou: %s", api_url, e)
                continue

        # 2. fallback HTML
        try:
            return self._fetch_html()[: self.max_jobs]
        except Exception as e:
            logger.warning("Eureca fetch HTML falhou: %s", e)
            return []

    def _fetch_api(self, url: str) -> list[RawJob]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
            r = c.get(url, params={"career_type": "internship", "limit": self.max_jobs})
            if r.status_code in (404, 403, 429):
                return []
            r.raise_for_status()
            # tenta json
            try:
                data = r.json()
            except Exception:
                return []
            items = None
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("data") or data.get("opportunities") or data.get("results")
            if not isinstance(items, list) or not items:
                return []
            raws: list[RawJob] = []
            for j in items[: self.max_jobs]:
                title = j.get("title") or j.get("name") or "Estágio Eureca"
                company = (
                    j.get("company") or j.get("company_name") or j.get("organization") or "Eureca"
                )
                if isinstance(company, dict):
                    company = company.get("name") or "Eureca"
                slug = j.get("slug") or j.get("id") or title
                url_job = (
                    j.get("url") or j.get("link") or f"https://app.eureca.me/oportunidade/{slug}"
                )
                desc = j.get("description") or j.get("about") or title
                loc = j.get("location") or j.get("city") or "Brasil - Remoto/Híbrido"
                raws.append(
                    RawJob(
                        external_id=f"eureca-{slug}",
                        title=str(title),
                        company_name=str(company),
                        url=str(url_job),
                        description=str(desc)[:3000] if desc else None,
                        location=str(loc) if loc else None,
                        raw_payload=j,
                    )
                )
            return raws

    def _fetch_html(self) -> list[RawJob]:
        params = {"career_type": "internship"}
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=HEADERS) as c:
            r = c.get(SEARCH_URL, params=params)
            r.raise_for_status()
            html = r.text

        if not html or "oportun" not in html.lower():
            logger.debug("Eureca HTML sem oportunidades")
            return []

        soup = BeautifulSoup(html, "lxml")
        raws: list[RawJob] = []
        seen: set[str] = set()

        # Eureca renderiza cards com links para /oportunidade/ ou /programa/
        links = soup.select('a[href*="/oportunidade/"], a[href*="/programa/"], a[href*="/vaga/"]')
        # fallback genérico: todos links com texto relevante
        if not links:
            links = [
                a
                for a in soup.select("a")
                if any(k in a.get_text().lower() for k in ["estágio", "estagio", "trainee"])
            ]

        for a in links:
            href = a.get("href", "").split("?")[0]
            if not href or href in seen:
                continue
            if href.startswith("/"):
                href = f"https://app.eureca.me{href}"
            if "eureca.me" not in href:
                continue
            seen.add(href)

            # título do card: tenta h3/h2 dentro do card ou texto do link
            container = a.find_parent(["div", "article", "li"])
            title = a.get_text(strip=True)
            if container:
                h = container.select_one("h2, h3, h4")
                if h and len(h.get_text(strip=True)) > 5:
                    title = h.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            # evita títulos genéricos
            if title.lower() in ("inscreva-se", "saiba mais", "ver vaga"):
                continue

            # empresa: texto próximo
            company = "Eureca"
            location = "Brasil"
            desc = None
            if container:
                txt = container.get_text(separator=" | ", strip=True)
                parts = [p.strip() for p in txt.split("|") if p.strip()]
                # heurística: empresa geralmente perto do título
                for p in parts[:3]:
                    if (
                        p != title
                        and len(p) < 60
                        and p.lower() not in ("hibrido", "remoto", "presencial")
                    ):
                        company = p
                        break
                # localização: procura por Brasil, Híbrido, Remoto
                for p in parts:
                    low = p.lower()
                    if any(
                        k in low
                        for k in [
                            "brasil",
                            "remoto",
                            "híbrido",
                            "hibrido",
                            "são paulo",
                            "rio de janeiro",
                        ]
                    ):
                        location = p
                        break
                desc = txt[:2500]

            # extrai id do href
            m = re.search(r"/(?:oportunidade|programa|vaga)/([^/]+)", href)
            ext_id = m.group(1) if m else href

            raws.append(
                RawJob(
                    external_id=f"eureca-{ext_id}",
                    title=title,
                    company_name=company,
                    url=href,
                    description=desc or title,
                    location=location,
                    raw_payload={"href": href},
                )
            )
            if len(raws) >= self.max_jobs:
                break
            time.sleep(0.1)

        logger.info("Eureca fetch HTML: %d vagas", len(raws))
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        loc = normalize_text(raw.location) or "Brasil"
        desc = raw.description
        full = f"{title} {desc or ''} {loc or ''}"
        techs = extract_technologies(full)
        seniority = extract_seniority(title, desc) or "intern"  # Eureca é majoritariamente estágio
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
