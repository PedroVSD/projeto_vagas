"""Fonte Demo - 100% legítima, sem ToS, para testes e desenvolvimento Fase 2."""

from __future__ import annotations

from app.services.deduplication import build_fingerprint
from app.services.normalization import (
    extract_modality,
    extract_seniority,
    extract_technologies,
    normalize_text,
)
from app.sources.base import JobSource, NormalizedJob, RawJob

DEMO_JOBS: list[dict] = [
    {
        "external_id": "demo-1",
        "title": "Junior Data Engineer",
        "company_name": "Empresa Demo",
        "url": "https://example.com/jobs/1",
        "description": (
            "Vaga Júnior com Python, SQL, Airflow e Docker - remoto Brasil. "
            "Requisitos: Python, SQL, Airflow."
        ),
        "location": "Brasil - Remoto",
    },
    {
        "external_id": "demo-2",
        "title": "Estágio MLOps",
        "company_name": "Tech Startup",
        "url": "https://example.com/jobs/2",
        "description": (
            "Estágio em MLOps: Python, Docker, Kubernetes, MLflow, AWS. Modalidade remota."
        ),
        "location": "Remoto",
    },
    {
        "external_id": "demo-3",
        "title": "Senior Data Engineer - NÃO RELEVANTE",
        "company_name": "Corp",
        "url": "https://example.com/jobs/3",
        "description": (
            "Vaga Sênior exige 8+ anos, presencial São Paulo, Java. Não deve pontuar alto."
        ),
        "location": "São Paulo, Presencial",
    },
]


class DemoSource(JobSource):
    name = "demo"

    def fetch_jobs(self) -> list[RawJob]:
        return [
            RawJob(
                external_id=j["external_id"],
                title=j["title"],
                company_name=j["company_name"],
                url=j["url"],
                description=j["description"],
                location=j["location"],
                raw_payload=j,
            )
            for j in DEMO_JOBS
        ]

    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        title = normalize_text(raw.title) or raw.title
        company = normalize_text(raw.company_name) or raw.company_name
        desc = raw.description
        loc = normalize_text(raw.location)
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
