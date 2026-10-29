"""Registry de fontes - adicionar/remover fontes sem modificar pipeline."""

from __future__ import annotations

from app.sources.academia import AcademiaSource
from app.sources.arbeitnow import ArbeitnowSource
from app.sources.base import JobSource
from app.sources.ciadetalentos import CiaDeTalentosSource
from app.sources.eureca import EurecaSource
from app.sources.getonbrd import GetOnBoardSource
from app.sources.greenhouse import GreenhouseSource
from app.sources.gupy import GupySource
from app.sources.jobicy import JobicySource
from app.sources.landingjobs import LandingJobsSource
from app.sources.linkedin import LinkedinSource
from app.sources.programathor import ProgramathorSource
from app.sources.remoteok import RemoteOkSource
from app.sources.vagas import VagasSource
from app.sources.weworkremotely import WeWorkRemotelySource

# Todas as fontes disponíveis (podem ser acionadas via POST /sources/ingest/{name})
ALL_SOURCES: list[JobSource] = [
    # Países-alvo atuais
    LinkedinSource(),
    GreenhouseSource(),
    JobicySource(),
    GetOnBoardSource(),
    RemoteOkSource(),
    WeWorkRemotelySource(),
    LandingJobsSource(),
    # Fontes Brasil mantidas para uso manual/opcional
    ArbeitnowSource(),
    VagasSource(),
    EurecaSource(),
    CiaDeTalentosSource(),
    AcademiaSource(),
    GupySource(),
    ProgramathorSource(),
]

# Pipeline padrão: apenas fontes alinhadas aos países-alvo
DEFAULT_SOURCES: list[JobSource] = [
    LinkedinSource(),
    GreenhouseSource(),
    JobicySource(),
    GetOnBoardSource(),
    RemoteOkSource(),
    WeWorkRemotelySource(),
    LandingJobsSource(),
]


def get_enabled_sources(names: list[str] | None = None) -> list[JobSource]:
    if not names:
        return DEFAULT_SOURCES
    by_name = {s.name: s for s in ALL_SOURCES}
    return [by_name[n] for n in names if n in by_name]


def get_source_by_name(name: str) -> JobSource | None:
    for s in ALL_SOURCES:
        if s.name == name:
            return s
    return None
