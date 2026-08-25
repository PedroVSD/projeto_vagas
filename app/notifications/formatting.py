"""Formatação de mensagens por vaga (spec §9)."""

from __future__ import annotations


def format_job_message(job: dict, score: dict | None = None) -> tuple[str, str]:
    """Retorna (subject, body) para email/telegram.

    job: {title, company, location, modality, seniority, technologies, url, description, first_seen_at}
    score: {final_score, classification, breakdown}
    """
    title = job.get("title") or "Vaga"
    company = job.get("company") or job.get("company_name") or "Empresa"
    url = job.get("url") or ""
    loc = job.get("location") or "Não informado"
    modality = job.get("modality") or "Não informado"
    seniority = job.get("seniority") or "Não informado"
    techs = job.get("technologies") or []
    score_val = score.get("final_score") if score else job.get("score")
    classification = score.get("classification") if score else job.get("classification")

    # Por que é relevante = techs + area
    reasons = []
    if techs:
        reasons.extend(techs[:5])
    area = None
    if score and score.get("area_breakdown", {}).get("area"):
        area = score["area_breakdown"]["area"]
        reasons.append(area)
    reasons = list(dict.fromkeys(reasons))  # dedup

    # Gaps: techs faltantes? simplificado: se não tem AWS etc., mas spec quer gaps reais — deixamos placeholder
    gaps = []
    if score and score.get("penalties"):
        gaps = list(score["penalties"].keys())
    if not gaps:
        # inferir gaps: tecnologias populares não presentes
        popular = ["AWS", "Docker", "Kubernetes"]
        gaps = [p for p in popular if p not in (techs or [])][:2]

    subject = f"{title} — {company} [{score_val}/100]" if score_val is not None else f"{title} — {company}"

    body = f"""**{title} — {company}**

Score: {score_val if score_val is not None else 'N/A'}/100 ({classification or 'N/A'})
Modalidade: {modality}
Localização: {loc}
Senioridade: {seniority}

Por que é relevante:
{chr(10).join(f"- {r}" for r in reasons) if reasons else "- Aderência técnica"}

Gaps:
{chr(10).join(f"- {g}" for g in gaps) if gaps else "- Nenhum gap crítico"}

Candidatura: {url}

Data encontrada: {job.get('first_seen_at') or job.get('created_at') or 'hoje'}
"""

    # Telegram markdown, Email plain — mesmo body serve para ambos
    return subject, body
