"""Fase 3 - Filtros heurísticos (pre-scoring determinístico)."""

from __future__ import annotations

import re


def is_relevant(job: dict) -> tuple[bool, str | None]:
    """Retorna (True, None) se relevante, (False, motivo) se descartar.

    Regras:
    - Se seniority = senior/staff e não for híbrido/remoto, descarta? Não, apenas penaliza depois.
    - Filtro bloqueante: vaga claramente não técnica ou exige >8 anos e é presencial fora BR.
    """
    hay = f"{job.get('title') or ''} {job.get('description') or ''}".lower()

    # Não-técnica bloqueante: se contém marketing/vendas e NÃO contém techs
    non_tech = [r"\bvendas\b", r"\bmarketing\b", r"\bvendedor\b"]
    has_non_tech = any(re.search(p, hay) for p in non_tech)
    has_tech = bool(job.get("technologies"))
    if has_non_tech and not has_tech:
        return False, "não técnica"

    # Experiência bloqueante: 10+ anos
    if re.search(r"\b10\+?\s*(anos|years)\b", hay):
        return False, "exige 10+ anos"

    return True, None
