"""Fase 2 - Normalização (título, modalidade, senioridade, tecnologias).

Usa matching determinístico por keywords - sem LLM, sem custo.
"""

from __future__ import annotations

import re

# Tecnologias do perfil (§1 spec) - normalizadas para matching case-insensitive
TECH_KEYWORDS: dict[str, list[str]] = {
    "Python": [r"\bpython\b"],
    "Go": [
        r"\bgolang\b",
        r"\bgo developer\b",
        r"\bgo engineer\b",
        r"\bdesenvolvedor go\b",
        r"\bdesarrollador go\b",
        r"\bbackend go\b",
    ],
    "SQL": [r"\bsql\b"],
    "Docker": [r"\bdocker\b"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Git": [r"\bgit\b", r"\bgithub\b"],
    "Linux": [r"\blinux\b"],
    "AWS": [r"\baws\b", r"\bamazon web services\b"],
    "GCP": [r"\bgcp\b", r"\bgoogle cloud\b"],
    "Azure": [r"\bazure\b"],
    "Airflow": [r"\bairflow\b"],
    "Spark": [r"\bspark\b", r"\bpyspark\b"],
    "Databricks": [r"\bdatabricks\b"],
    "MLflow": [r"\bmlflow\b"],
    "CI/CD": [r"\bci/cd\b", r"\bci\\cd\b"],
    "PostgreSQL": [r"\bpostgres"],
    "Redis": [r"\bredis\b"],
    "Kafka": [r"\bkafka\b"],
    "Machine Learning": [r"\bmachine learning\b", r"\bml\b"],
    "NLP": [r"\bnlp\b", r"\bnatural language"],
    "LLM": [r"\bllm\b", r"\bgenerative ai\b", r"\bgen ai\b"],
    "MLOps": [r"\bmlops\b"],
    "Data Engineering": [r"\bdata engineer"],
    "Cloud": [r"\bcloud\b"],
}

SENIORITY_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "intern",
        [
            r"\best[áa]gio\b",
            r"\bintern\b",
            r"\binternship\b",
            r"\bpasant[íi]a\b",
            r"\bpracticante\b",
            r"\bbecari[oa]\b",
        ],
    ),
    ("junior", [r"\bj[úu]nior\b", r"\bjunior\b", r"\bjr\.?\b"]),
    ("entry_level", [r"\bentry.level\b", r"\bentry level\b", r"\bearly career\b"]),
    ("trainee", [r"\btrainee\b", r"\baprendiz\b"]),
    (
        "pleno",
        [
            r"\bpleno\b",
            r"\bmid.level\b",
            r"\bmid level\b",
            r"\bintermediate\b",
            r"\bsemi.?senior\b",
            r"\bssr\b",
        ],
    ),
    ("senior", [r"\bs[eê]nior\b", r"\bsenior\b", r"\bsr\.?\b"]),
    (
        "staff",
        [
            r"\bstaff (engineer|software|developer|data)\b",
            r"\bprincipal (engineer|software|developer|data)\b",
            r"\b(tech|team) lead\b",
            r"\blead (engineer|developer|software|data)\b",
            r"\bl[íi]der (t[ée]cnico|de (equipe|projeto))\b",
        ],
    ),
]

MODALITY_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "remoto_brasil",
        [
            r"\bremoto.*brasil\b",
            r"\bremote.*brazil\b",
            r"\bbrasil.*remoto\b",
            r"\bremote.*chile\b",
            r"\bremoto.*chile\b",
            r"\bchile.*remoto\b",
            r"\bremote.*argentina\b",
            r"\bremoto.*argentina\b",
            r"\bargentina.*remoto\b",
        ],
    ),
    (
        "remoto",
        [
            r"\bremoto\b",
            r"\bremote\b",
            r"\b100% remoto\b",
            r"\bfully remote\b",
            r"\bteletrabajo\b",
            r"\btrabajo remoto\b",
        ],
    ),
    ("hibrido", [r"\bh[íi]brid[oa]\b", r"\bhybrid\b"]),
    (
        "presencial",
        [r"\bpresencial\b", r"\bon.site\b", r"\bonsite\b", r"\ben oficina\b"],
    ),
]


def _match(text: str, patterns: list[str]) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in patterns)


def extract_technologies(text: str) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for tech, patterns in TECH_KEYWORDS.items():
        if _match(text, patterns):
            found.append(tech)
    return found


def extract_seniority(title: str, description: str | None = None) -> str | None:
    # O título é a fonte mais confiável; descrições costumam citar "lead/junior"
    # em contexto de mentoria ou requisitos e geram falso positivo.
    title_low = (title or "").lower()
    for level, patterns in SENIORITY_PATTERNS:
        if _match(title_low, patterns):
            return level

    if not description:
        return None
    desc_low = description.lower()
    # Na descrição, considera apenas níveis de entrada/intermediários.
    # Sênior/staff só são aceitos quando aparecem no título.
    for level, patterns in SENIORITY_PATTERNS:
        if level in ("senior", "staff"):
            continue
        if _match(desc_low, patterns):
            return level
    return None


def extract_modality(location: str | None, description: str | None = None) -> str | None:
    hay = f"{location or ''} {description or ''}".lower()
    for modality, patterns in MODALITY_PATTERNS:
        if _match(hay, patterns):
            return modality
    # fallback: se location contém brasil + remoto já capturado, senão remoto genérico
    if location and "brasil" in location.lower() and "remoto" in hay:
        return "remoto_brasil"
    return None


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    return v if v else None
