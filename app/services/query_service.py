"""Fase 3 - Queries configuráveis: loader YAML + DB sync."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore
from sqlalchemy.orm import Session

from app.models.search_query import SearchQuery


def load_queries_from_yaml(
    path: str | Path = "config/search_queries.yaml",
) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"simple": [], "boolean": [], "search_profiles": {}, "settings": {}}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {
        "simple": data.get("simple", []),
        "boolean": data.get("boolean", []),
        "search_profiles": data.get("search_profiles", {}),
        "settings": data.get("settings", {}),
    }


def get_all_queries(path: str | Path = "config/search_queries.yaml") -> list[dict[str, Any]]:
    data = load_queries_from_yaml(path)
    return data["simple"] + data["boolean"]


def get_search_profiles(path: str | Path = "config/search_queries.yaml") -> dict[str, Any]:
    """Retorna search_profiles do YAML (markdown/buscas_booleanas_vagas.md §11)."""
    return load_queries_from_yaml(path).get("search_profiles", {})


def get_queries_by_family(
    family: str, path: str | Path = "config/search_queries.yaml"
) -> list[dict[str, Any]]:
    return [q for q in get_all_queries(path) if q.get("family") == family]


def sync_queries_to_db(db: Session, path: str | Path = "config/search_queries.yaml") -> int:
    """Sincroniza YAML -> DB (idempotente, cria se não existir)."""
    queries = get_all_queries(path)
    count = 0
    for q in queries:
        text = q.get("query")
        family = q.get("family")
        if not text:
            continue
        exists = db.query(SearchQuery).filter(SearchQuery.query_text == text).first()
        if not exists:
            db.add(SearchQuery(query_text=text, family=family, enabled=True))
            count += 1
    db.commit()
    return count
