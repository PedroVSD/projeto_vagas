"""Registry de fontes - adicionar/remover fontes sem modificar pipeline."""

from __future__ import annotations

from app.sources.academia import AcademiaSource
from app.sources.arbeitnow import ArbeitnowSource
from app.sources.base import JobSource
from app.sources.ciadetalentos import CiaDeTalentosSource
from app.sources.demo import DemoSource
from app.sources.eureca import EurecaSource
from app.sources.greenhouse import GreenhouseSource
from app.sources.gupy import GupySource
from app.sources.linkedin import LinkedinSource
from app.sources.programathor import ProgramathorSource
from app.sources.vagas import VagasSource

# Instâncias padrão (Fase 2 + expansão perfil Júnior/Estágio BR + Gupy/Programathor/Greenhouse)
DEFAULT_SOURCES: list[JobSource] = [
    DemoSource(),
    ArbeitnowSource(),
    LinkedinSource(),
    VagasSource(),
    EurecaSource(),
    CiaDeTalentosSource(),
    AcademiaSource(),
    GupySource(),
    ProgramathorSource(),
    GreenhouseSource(),
]


def get_enabled_sources(names: list[str] | None = None) -> list[JobSource]:
    if not names:
        return DEFAULT_SOURCES
    by_name = {s.name: s for s in DEFAULT_SOURCES}
    return [by_name[n] for n in names if n in by_name]


def get_source_by_name(name: str) -> JobSource | None:
    for s in DEFAULT_SOURCES:
        if s.name == name:
            return s
    return None
