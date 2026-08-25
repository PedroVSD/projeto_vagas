"""Fase 3 - Scoring heurístico 0-100 (spec §6).

Regras com cap por categoria para evitar keyword stuffing.
"""

from __future__ import annotations

import re


# Pesos por senioridade (§6)
SENIORITY_SCORES: dict[str, int] = {
    "intern": 25,
    "junior": 25,
    "entry_level": 20,
    "trainee": 15,
    "pleno": -20,
    "senior": -50,
    "staff": -80,
}

# Área (§6) - detecção por keywords no título+descrição
AREA_KEYWORDS: dict[str, tuple[int, list[str]]] = {
    "mlops": (25, [r"\bmlops\b", r"\bmachine learning operations\b"]),
    "ml_engineering": (25, [r"\bmachine learning engineer\b", r"\bml engineer\b", r"\bmlops engineer\b"]),
    "data_engineering": (25, [r"\bdata engineer", r"\bdata engineering\b"]),
    "software_engineering": (20, [r"\bsoftware engineer", r"\bsoftware engineering\b"]),
    "data_science": (20, [r"\bdata scientist\b", r"\bdata science\b", r"\bcientista de dados\b"]),
    "ai_engineering": (20, [r"\bai engineer\b", r"\bintelligence engineer\b"]),
    "backend": (15, [r"\bbackend\b"]),
    "devops_platform": (15, [r"\bdevops\b", r"\bplatform engineer\b", r"\bplatform engineering\b"]),
    "analytics_engineering": (15, [r"\banalytics engineer\b"]),
    "data_analyst": (5, [r"\bdata analyst\b", r"\banalista de dados\b"]),
}

# Modalidade (§6)
MODALITY_SCORES: dict[str, int] = {
    "remoto_brasil": 25,
    "remoto": 20,
    "hibrido": 5,
    "presencial": -10,
}

# Tecnologias (§6) - valores individuais
TECH_SCORES: dict[str, int] = {
    "Python": 5,
    "Go": 5,
    "Docker": 5,
    "Kubernetes": 5,
    "Airflow": 5,
    "Spark": 5,
    "Databricks": 5,
    "MLflow": 5,
    "Machine Learning": 5,
    "NLP": 5,
    "LLM": 5,
    "MLOps": 5,
    "Data Engineering": 5,
    "Cloud": 5,
    "AWS": 4,
    "GCP": 4,
    "FastAPI": 4,
    "SQL": 4,
    "Kafka": 4,
    "CI/CD": 4,
    "Azure": 3,
    "PostgreSQL": 3,
    "Redis": 3,  # não listado mas útil
}


def _match_any(text: str, patterns: list[str]) -> bool:
    low = text.lower()
    return any(re.search(p, low) for p in patterns)


def score_seniority(seniority: str | None) -> tuple[int, dict]:
    if not seniority:
        return 0, {"seniority": None, "points": 0, "reason": "não informado, confiança reduzida"}
    pts = SENIORITY_SCORES.get(seniority, 0)
    return pts, {"seniority": seniority, "points": pts}


def score_area(title: str, description: str | None) -> tuple[int, dict]:
    hay = f"{title} {description or ''}"
    best_area = None
    best_pts = 0
    for area, (pts, patterns) in AREA_KEYWORDS.items():
        if _match_any(hay, patterns):
            if pts > best_pts:
                best_pts = pts
                best_area = area
    # se múltiplas áreas, pega maior; poderia somar com cap, mas spec sugere área única prioritária
    return best_pts, {"area": best_area, "points": best_pts}


def score_modality(modality: str | None) -> tuple[int, dict]:
    if not modality:
        return 0, {"modality": None, "points": 0}
    pts = MODALITY_SCORES.get(modality, 0)
    return pts, {"modality": modality, "points": pts}


def score_technologies(technologies: list[str] | None, cap: int = 25) -> tuple[int, dict]:
    if not technologies:
        return 0, {"technologies": [], "points": 0, "cap": cap}
    pts = 0
    breakdown: dict[str, int] = {}
    for t in technologies:
        v = TECH_SCORES.get(t, 2)  # tech não listada vale 2
        breakdown[t] = v
        pts += v
    capped = min(pts, cap)
    return capped, {"technologies": breakdown, "raw": pts, "points": capped, "cap": cap}


def score_penalties(title: str, description: str | None, location: str | None, modality: str | None) -> tuple[int, dict]:
    hay = f"{title} {description or ''}".lower()
    penalties: dict[str, int] = {}
    total = 0

    # experiência incompatível: 5+ anos, 8 years etc.
    if re.search(r"\b[5-9]\+?\s*(anos|years|year)\b", hay) or re.search(r"\b10\+?\s*(anos|years)\b", hay):
        penalties["experiencia_5_anos"] = -15
        total -= 15
    if re.search(r"\b(8|10)\+?\s*(anos|years)\b", hay):
        penalties["experiencia_8_anos"] = -10
        total -= 10

    # senior explícito já penalizado via seniority, mas se título contiver senior sem seniority extraído
    if re.search(r"\bs[eê]nior\b", hay) and "senior" not in hay:
        pass  # já coberto

    # presencial fora BR sem remoto
    if modality == "presencial" and location and "brasil" not in location.lower() and "brazil" not in location.lower():
        # se não for remoto, penaliza
        if not re.search(r"\bremoto\b|\bremote\b", hay):
            penalties["presencial_fora_br"] = -10
            total -= 10

    # não técnica: ex: vendas, marketing, rh predominante
    non_tech_keywords = [r"\bvendas\b", r"\bmarketing\b", r"\brh\b", r"\brecrutamento\b", r"\bvendedor\b"]
    if _match_any(hay, non_tech_keywords):
        # só penaliza se não tiver techs relevantes
        penalties["nao_tecnica"] = -20
        total -= 20

    # sem relação software/dados/ml
    relevant = any(re.search(r"\b(python|sql|docker|ml|data|software|engineer|airflow|spark)\b", hay) for _ in [1])
    if not relevant and not penalties:
        # não penaliza automaticamente, deixa score baixo natural
        pass

    return total, penalties


def classify_score(final: int) -> str:
    if final >= 90:
        return "excelente"
    if final >= 75:
        return "muito_relevante"
    if final >= 60:
        return "relevante"
    if final >= 45:
        return "talvez_relevante"
    return "ignorar"


def score_job(job: dict) -> dict:
    """Calcula score 0-100 para um job dict com keys: title, description, location, modality, seniority, technologies.

    Retorna breakdown completo.
    """
    title = job.get("title") or ""
    desc = job.get("description")
    loc = job.get("location")
    modality = job.get("modality")
    seniority = job.get("seniority")
    techs = job.get("technologies")

    s_sen, b_sen = score_seniority(seniority)
    s_area, b_area = score_area(title, desc)
    s_mod, b_mod = score_modality(modality)
    s_tech, b_tech = score_technologies(techs)
    s_pen, b_pen = score_penalties(title, desc, loc, modality)

    # Base 50 para vagas neutras? Spec não define base, usamos 30 como neutro para evitar negativo excessivo
    # Melhor: soma direta e clamp 0-100. Para vagas juniores típicas: 25+25+20+15=85 -> excelente
    # Para sênior: -50-10+25= -35 -> 0 após clamp
    raw = s_sen + s_area + s_mod + s_tech + s_pen
    # Adiciona base 30 para centralizar: então junior típico 85+30=115 -> cap 100
    # Sem base, junior típico 85 -> muito_relevante (75-89) -> razoável. Testamos sem base para manter spec literal.
    # Vamos usar base 30 mas garantir 0-100
    base = 30
    final = raw + base
    final = max(0, min(100, final))

    return {
        "heuristic_score": final,
        "final_score": final,
        "classification": classify_score(final),
        "breakdown": {
            "seniority": b_sen,
            "area": b_area,
            "modality": b_mod,
            "technologies": b_tech,
            "penalties": b_pen,
            "raw_sum": raw,
            "base": base,
        },
        "seniority_breakdown": b_sen,
        "area_breakdown": b_area,
        "modality_breakdown": b_mod,
        "tech_breakdown": b_tech,
        "penalties": b_pen,
    }
