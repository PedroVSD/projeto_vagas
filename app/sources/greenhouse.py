"""Fonte Greenhouse - API pública oficial.

Docs: https://developers.greenhouse.io/job-board
- Endpoint público sem auth: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
- Usada por centenas de empresas (lista configurável).
- Respeita ToS: API oficial, sem scraping.
- Board tokens via config/env GUPY não - GREENHOUSE_BOARDS env ou default lista demo.

Para operacional BR: adicionar boards de empresas que contratam Júnior BR
(ex: inserir tokens reais em GREENHOUSE_BOARDS).

Se nenhum board configurado, tenta lista demo pública e retorna [] se vazia.
"""

from __future__ import annotations

import logging
import os

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

DEFAULT_BOARDS = [
    # boards públicos demo - empresas com programas júnior/estágio
    # podem ser vazios; pipeline isola por fonte e continua
    "greenhouse",
]

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"


class GreenhouseSource(JobSource):
    """Adapter Greenhouse Job Board API."""

    name = "greenhouse"

    def __init__(self, boards: list[str] | None = None, timeout: int = 12, max_per_board: int = 10):
        env_boards = os.getenv("GREENHOUSE_BOARDS", "")
        if boards is None and env_boards:
            boards = [b.strip() for b in env_boards.split(",") if b.strip()]
        self.boards = boards or DEFAULT_BOARDS
        self.timeout = timeout
        self.max_per_board = max_per_board

    def fetch_jobs(self) -> list[RawJob]:
        all_raws: list[RawJob] = []
        seen: set[str] = set()
        for board in self.boards:
            try:
                raws = self._fetch_board(board)
                for r in raws:
                    if r.url not in seen:
                        seen.add(r.url)
                        all_raws.append(r)
            except Exception as e:
                logger.warning("Greenhouse board '%s' falhou: %s", board, e)
                continue
        logger.info("Greenhouse fetch: %d vagas (boards=%d)", len(all_raws), len(self.boards))
        return all_raws

    def _fetch_board(self, board: str) -> list[RawJob]:
        url = API_URL.format(board=board)
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as c:
            r = c.get(url, headers={"Accept": "application/json"})
            if r.status_code in (404, 403, 429):
                logger.debug("Greenhouse board %s status %s", board, r.status_code)
                return []
            r.raise_for_status()
            data = r.json()
        jobs = data.get("jobs") if isinstance(data, dict) else data
        if not isinstance(jobs, list):
            return []
        # filtra para Júnior/Estágio quando possível para reduzir ruído
        raws: list[RawJob] = []
        for j in jobs[: self.max_per_board * 2]:
            title = j.get("title") or ""
            # filtro leve: prioriza junior/intern mas não exclui tudo (scoring fará o resto)
            # aqui apenas limita para não trazer 200 cargos sênior desnecessários
            low = title.lower()
            if not any(k in low for k in ["junior", "jr", "intern", "estágio", "estagio", "trainee", "entry", "python", "data", "mlops", "software"]):
                # se título não tem nenhum termo relevante, pula para manter quota útil
                # mas mantém pelo menos 2 por board para não ficar vazio
                if len(raws) >= 2:
                    continue
            company = j.get("company") or board
            loc_obj = j.get("location") or {}
            location = loc_obj.get("name") if isinstance(loc_obj, dict) else str(loc_obj) if loc_obj else None
            absolute_url = j.get("absolute_url") or j.get("url") or f"https://boards.greenhouse.io/{board}/jobs/{j.get('id','')}"
            desc = j.get("content") or j.get("updated_at") or title
            # greenhouse content é HTML
            if desc and "<" in desc:
                # mantém HTML cru para scoring extrair techs mas limita
                desc = desc[:4000]
            raws.append(
                RawJob(
                    external_id=f"greenhouse-{board}-{j.get('id')}",
                    title=str(title),
                    company_name=str(company) if isinstance(company, str) else board,
                    url=str(absolute_url),
                    description=str(desc)[:4000] if desc else None,
                    location=str(location) if location else None,
                    raw_payload={"board": board, **j},
                )
            )
            if len(raws) >= self.max_per_board:
                break
        return raws

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        loc = normalize_text(raw.location)
        desc = raw.description
        full = f"{title} {desc or ''} {loc or ''}"
        techs = extract_technologies(full)
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
