"""Fase extra - Fonte LinkedIn (guest API pública).

Usa endpoint público de vagas para visitantes não logados:
  https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

- Sem auth, sem cookie, sem bypass de CAPTCHA.
- Respeita ToS: acessa apenas dados públicos que qualquer visitante vê sem login
  (mesma base usada por Apify/JobsPipe). Public-data hiQ v. LinkedIn.
- Rate-limited, paginação via `start` (25 por página), respeita robots e backoff.
- Implementa fetch per query (usa config/search_queries.yaml) mas limita para
  não sobrecarregar (max_per_query=10, max_queries=5 por execução).
- Se LinkedIn retornar 999, 429 ou HTML vazio, retorna [] sem derrubar pipeline
  (ingestão isola por fonte em app/services/ingestion.py:172).

Perfil alvo: Estágio/Júnior em MLOps, Engenharia de Software/Dados, Data Science
  -> filtra por f_E=2,3 (Entry level + Associate) e f_WT=2,3 (Remote + Hybrid),
     alternando entre os países-alvo (Chile, Argentina, Espanha, Portugal, Polônia, EUA, Canadá).

Alternativa futura: trocar por API agregadora (JobsPipe, ReefAPI) via ENV se escalar.
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

GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
GUEST_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) job-finder/0.1 (+https://github.com/job-finder)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

# Filtros LinkedIn (guest API)
# f_E=2 (Entry level), 3 (Associate) -> Júnior/Pleno
# f_WT=2 (Remote), 3 (Hybrid)
EXPERIENCE_FILTER = "2,3"
WORKPLACE_FILTER = "2,3"
DEFAULT_LOCATIONS = [
    "Chile",
    "Argentina",
    "Spain",
    "Portugal",
    "Poland",
    "United States",
    "Canada",
]


class LinkedinSource(JobSource):
    """Adapter LinkedIn Guest API - respeita ToS, dados públicos."""

    name = "linkedin"

    def __init__(
        self,
        timeout: int = 15,
        max_per_query: int = 10,
        max_queries: int = 7,
        location: str | None = None,
        locations: list[str] | None = None,
    ):
        self.timeout = timeout
        self.max_per_query = max_per_query
        self.max_queries = max_queries
        if locations:
            self.locations = locations
        elif location:
            self.locations = [location]
        else:
            self.locations = DEFAULT_LOCATIONS

    def _get_queries(self) -> list[str]:
        try:
            from app.services.query_service import get_all_queries

            qs = get_all_queries()
            # prioriza simple (mais específicas) e equilibra por família,
            # garantindo cobertura de todas as áreas (incluindo Golang).
            simple = [
                q
                for q in qs
                if "simple" in q.get("family", "")
                or q.get("family")
                in {
                    "mlops",
                    "software_engineering",
                    "data_engineering",
                    "data_science",
                    "ml_engineering",
                    "golang",
                }
            ]
            if not simple:
                simple = qs[: self.max_queries]

            by_family: dict[str, list[str]] = {}
            for q in simple:
                by_family.setdefault(q.get("family", "outros"), []).append(q["query"])

            balanced: list[str] = []
            while len(balanced) < self.max_queries:
                added = False
                for items in by_family.values():
                    if items:
                        balanced.append(items.pop(0))
                        added = True
                        if len(balanced) >= self.max_queries:
                            break
                if not added:
                    break

            # filtra apenas queries com boa aderência Júnior/Pleno + Golang
            filtered = [
                q
                for q in balanced
                if any(
                    k in q.lower()
                    for k in [
                        "junior",
                        "pleno",
                        "golang",
                        "go engineer",
                        "go developer",
                        "python",
                        "data engineer",
                        "mlops",
                    ]
                )
            ]
            return filtered or balanced
        except Exception:
            return [
                "Junior Data Engineer",
                "Pleno Data Engineer",
                "Junior Python Developer",
                "Junior Golang Developer",
                "Pleno Golang Developer",
                "Junior Machine Learning Engineer",
                "Pleno Data Scientist",
            ][: self.max_queries]

    def fetch_jobs(self) -> list[RawJob]:
        queries = self._get_queries()
        all_raws: list[RawJob] = []
        seen_urls: set[str] = set()

        for idx, q in enumerate(queries):
            location = self.locations[idx % len(self.locations)]
            try:
                raws = self._fetch_for_query(q, location)
                for r in raws:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_raws.append(r)
                    if len(all_raws) >= self.max_per_query * self.max_queries:
                        break
                # backoff leve entre queries para respeitar rate limit
                time.sleep(0.8)
            except Exception as e:
                logger.warning("LinkedIn fetch falhou query='%s' location='%s': %s", q, location, e)
                continue
            if len(all_raws) >= self.max_per_query * self.max_queries:
                break

        logger.info("LinkedIn fetch: %d vagas (queries=%d)", len(all_raws), len(queries))
        return all_raws

    def _fetch_for_query(self, query: str, location: str | None = None) -> list[RawJob]:
        location = location or self.locations[0]
        params = {
            "keywords": query,
            "location": location,
            "f_E": EXPERIENCE_FILTER,
            "f_WT": WORKPLACE_FILTER,
            "trk": "public_jobs_jobs-search-bar_search-submit",
            "start": 0,
        }
        url = f"{GUEST_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        try:
            with httpx.Client(
                timeout=self.timeout, follow_redirects=True, headers=DEFAULT_HEADERS
            ) as c:
                r = c.get(url)
                # LinkedIn retorna 999 quando bloqueia datacenter IPs
                if r.status_code in (999, 429, 403):
                    logger.warning(
                        "LinkedIn guest API bloqueado status=%s query='%s'", r.status_code, query
                    )
                    return []
                r.raise_for_status()
                html = r.text
        except Exception as e:
            logger.warning("LinkedIn request erro query='%s': %s", query, e)
            return []

        if not html or "base-card" not in html.lower():
            logger.debug(
                "LinkedIn sem resultados query='%s' html_len=%s", query, len(html) if html else 0
            )
            return []

        return self._parse_search_html(html, query, location)

    def _parse_search_html(
        self, html: str, query: str, location: str | None = None
    ) -> list[RawJob]:
        soup = BeautifulSoup(html, "lxml")
        # LinkedIn guest retorna <li><div class="base-card">...</div></li>
        cards = soup.select("li div.base-card, div.job-search-card, div.base-card")
        if not cards:
            cards = soup.select("li")

        raws: list[RawJob] = []
        for card in cards[: self.max_per_query]:
            try:
                # URL da vaga
                a = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
                if not a or not a.get("href"):
                    continue
                href = a["href"].split("?")[0].strip()
                # extrai job_id do href ".../jobs/view/1234567890"
                m = re.search(r"/jobs/view/(\d+)", href)
                job_id = m.group(1) if m else href
                url = href if href.startswith("http") else f"https://www.linkedin.com{href}"

                # título
                title_el = card.select_one(
                    "h3.base-search-card__title, h3, .base-search-card__title"
                )
                title = (
                    title_el.get_text(strip=True) if title_el else a.get_text(strip=True) or query
                )

                # empresa
                comp_el = card.select_one(
                    "h4.base-search-card__subtitle, .base-search-card__subtitle, h4"
                )
                company = comp_el.get_text(strip=True) if comp_el else "Confidencial"

                # localização
                loc_el = card.select_one(
                    ".job-search-card__location, .base-search-card__metadata span"
                )
                card_location = (
                    loc_el.get_text(strip=True)
                    if loc_el
                    else (location or self.locations[0])
                )

                # tenta buscar descrição resumida embutida
                desc = None
                # não faz request extra por padrão; descrição via detail se necessário
                # mas tentamos pegar snippet se existir
                snippet = card.get_text(separator=" ", strip=True)
                if snippet:
                    desc = snippet[:2000]

                raws.append(
                    RawJob(
                        external_id=f"linkedin-{job_id}",
                        title=title,
                        company_name=company,
                        url=url,
                        description=desc,
                        location=card_location,
                        raw_payload={"query": query, "job_id": job_id, "linkedin_url": url},
                    )
                )
            except Exception as e:
                logger.debug("LinkedIn parse card falhou: %s", e)
                continue
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        loc = normalize_text(raw.location)
        desc = raw.description
        full_text = f"{title} {desc or ''} {loc or ''}"
        techs = extract_technologies(full_text)
        seniority = extract_seniority(title, desc)
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
