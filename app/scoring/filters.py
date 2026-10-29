"""Fase 3 - Filtros heurísticos (pre-scoring determinístico)."""

from __future__ import annotations

import re


def is_relevant(job: dict) -> tuple[bool, str | None]:
    """Retorna (True, None) se relevante, (False, motivo) se descartar.

    Regras:
    - Perfil aceita apenas Júnior ou Pleno; descarta níveis explícitos fora disso.
    - Perfil aceita apenas remoto ou híbrido; descarta presencial explícito.
    - Filtro bloqueante: vaga claramente não técnica ou exige 10+ anos.
    """
    hay = f"{job.get('title') or ''} {job.get('description') or ''}".lower()

    # Não-técnica bloqueante: se contém marketing/vendas e NÃO contém techs
    non_tech = [r"\bvendas\b", r"\bmarketing\b", r"\bvendedor\b"]
    has_non_tech = any(re.search(p, hay) for p in non_tech)
    has_tech = bool(job.get("technologies"))
    if has_non_tech and not has_tech:
        return False, "não técnica"

    # Senioridade: apenas junior ou pleno
    seniority = job.get("seniority")
    if seniority and seniority not in ("junior", "pleno"):
        return False, f"senioridade fora do perfil ({seniority})"
    senior_pattern = r"\b(s[eê]nior|senior|staff|principal|lead|l[íi]der)\b"
    if seniority is None and re.search(senior_pattern, hay):
        return False, "senioridade fora do perfil"

    # Modalidade: apenas remoto ou híbrido
    if job.get("modality") == "presencial":
        return False, "presencial fora do perfil"

    # Experiência bloqueante: 10+ anos
    if re.search(r"\b10\+?\s*(anos|years)\b", hay):
        return False, "exige 10+ anos"

    return True, None
