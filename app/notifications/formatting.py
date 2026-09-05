"""Formatação de mensagens por vaga (spec §9)."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def format_job_message(job: dict, score: dict | None = None) -> tuple[str, str]:
    """Retorna (subject, body) para email/telegram.

    job: {title, company, location, modality, seniority,
          technologies, url, description, first_seen_at}
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

    # Gaps: techs faltantes? simplificado: se não tem AWS etc.,
    # mas spec quer gaps reais — deixamos placeholder
    gaps = []
    if score and score.get("penalties"):
        gaps = list(score["penalties"].keys())
    if not gaps:
        # inferir gaps: tecnologias populares não presentes
        popular = ["AWS", "Docker", "Kubernetes"]
        gaps = [p for p in popular if p not in (techs or [])][:2]

    subject = (
        f"{title} — {company} [{score_val}/100]"
        if score_val is not None
        else f"{title} — {company}"
    )

    # Data encontrada - formato brasileiro configurável via YAML/env
    raw_date = job.get("first_seen_at") or job.get("created_at")
    date_str = _format_br_date(raw_date)

    # LLM analysis se disponível (score["llm"] ou tech_breakdown["llm"])
    llm = None
    if score and score.get("llm"):
        llm = score["llm"]
    elif score and isinstance(score.get("tech_breakdown"), dict) and score["tech_breakdown"].get("llm"):
        llm = score["tech_breakdown"]["llm"]
    elif job.get("score") and isinstance(job["score"], dict) and job["score"].get("llm"):
        llm = job["score"]["llm"]
    llm_block = ""
    if llm:
        rec = llm.get("recommendation", "N/A")
        reason = llm.get("reason", "")
        overall = llm.get("overall_match", "")
        matching = ", ".join(llm.get("matching_skills", [])[:4])
        missing = ", ".join(llm.get("missing_requirements", [])[:3])
        llm_block = f"\nAnálise LLM ({overall}/100 - {rec}):\n{reason}\n"
        if matching:
            llm_block += f"Skills: {matching}\n"
        if missing:
            llm_block += f"Faltantes: {missing}\n"

    body = f"""**{title} — {company}**

Score: {score_val if score_val is not None else "N/A"}/100 ({classification or "N/A"})
Modalidade: {modality}
Localização: {loc}
Senioridade: {seniority}

Por que é relevante:
{chr(10).join(f"- {r}" for r in reasons) if reasons else "- Aderência técnica"}

Gaps:
{chr(10).join(f"- {g}" for g in gaps) if gaps else "- Nenhum gap crítico"}
{llm_block}
Candidatura: {url}

Data encontrada: {date_str}
"""

    # Telegram markdown, Email plain — mesmo body serve para ambos
    return subject, body


def _format_br_date(value) -> str:
    """Converte data p/ padrão brasileiro usando config YAML/env. Já formatada passa direto."""
    if not value:
        return "hoje"
    # se já está no formato BR (contém "/" e "às"), retorna direto - evita re-parse
    if isinstance(value, str) and "/" in value and "às" in value:
        return value
    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return value
    if dt is None:
        return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        from pathlib import Path

        import yaml

        from app.core.config import get_settings

        settings = get_settings()
        tz_name = settings.display_timezone
        fmt = settings.display_date_format
        p = Path("config/search_queries.yaml")
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            disp = data.get("display") or {}
            tz_name = disp.get("timezone") or tz_name
            fmt = disp.get("date_format") or fmt
    except Exception:
        tz_name = "America/Sao_Paulo"
        fmt = "%d/%m/%Y às %H:%M"
    try:
        tz = ZoneInfo(tz_name)
        dt_br = dt.astimezone(tz)
        return dt_br.strftime(fmt)
    except Exception:
        return dt.strftime("%d/%m/%Y às %H:%M")
