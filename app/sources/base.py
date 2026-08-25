"""Fase 2 - Interface abstrata JobSource.

Spec §4 e §13: arquitetura modular, cada fonte implementa fetch_jobs() + normalize_job()
sem modificar pipeline. Respeita ToS - só usa APIs/feeds oficiais, nunca bypass.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawJob:
    """Payload bruto retornado pela fonte antes de normalização."""

    external_id: str
    title: str
    company_name: str
    url: str
    description: str | None = None
    location: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedJob:
    """Job normalizado pronto para deduplicação/persistência.

    Campos alinhados com app/models/job.py
    """

    title: str
    company_name: str
    url: str
    description: str | None = None
    location: str | None = None
    modality: str | None = None  # remoto, remoto_brasil, hibrido, presencial
    seniority: str | None = None  # intern, junior, entry_level, trainee, pleno, senior
    technologies: list[str] | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fingerprint: str | None = None  # preenchido por deduplication


class JobSource(ABC):
    """Interface - toda fonte deve implementar."""

    name: str  # identificador único (ex: "arbeitnow", "demo")

    @abstractmethod
    def fetch_jobs(self) -> list[RawJob]:
        """Busca vagas novas desde a última execução. Não persiste."""
        ...

    @abstractmethod
    def normalize_job(self, raw: RawJob) -> NormalizedJob:
        """Converte RawJob -> NormalizedJob (sem fingerprint)."""
        ...

    def fetch_and_normalize(self) -> list[NormalizedJob]:
        """Helper: fetch + normalize em lote."""
        raws = self.fetch_jobs()
        return [self.normalize_job(r) for r in raws]
