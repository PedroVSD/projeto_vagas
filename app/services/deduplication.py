"""Fase 2 - Deduplicação via fingerprint estável.

Spec §3: fingerprint = hash(company + title + location + url + description_hash)
Mesma vaga em múltiplas fontes -> único registro.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata


def _normalize(s: str | None) -> str:
    if not s:
        return ""
    # remove acentos, lower, strip, collapsa espaços
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def build_fingerprint(
    company: str,
    title: str,
    location: str | None,
    url: str,
    description: str | None = None,
) -> str:
    """Gera fingerprint estável (sha256 hex, 64 chars, armazenado como 128).

    Usa url como âncora principal - se mesma empresa+titulo mas url diferente,
    gera fingerprints diferentes. Description usa apenas hash dos primeiros 500 chars
    para evitar sensibilidade a mudanças pequenas.
    """
    desc_hash = ""
    if description:
        desc_norm = _normalize(description)[:500]
        desc_hash = hashlib.sha256(desc_norm.encode()).hexdigest()[:16]

    base = "|".join(
        [
            _normalize(company),
            _normalize(title),
            _normalize(location),
            _normalize(url),
            desc_hash,
        ]
    )
    return hashlib.sha256(base.encode()).hexdigest()


def fingerprint_for_normalized(job_dict: dict) -> str:
    return build_fingerprint(
        company=job_dict.get("company_name") or job_dict.get("company") or "",
        title=job_dict.get("title") or "",
        location=job_dict.get("location"),
        url=job_dict.get("url") or "",
        description=job_dict.get("description"),
    )
