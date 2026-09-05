"""LLM Classification - suporta Ollama e OpenAI via interface única.

Uso:
    from app.scoring.llm import get_llm_provider

    provider = get_llm_provider()
    if provider.is_enabled():
        result = provider.classify(job_dict)

Custo controlado: chamar apenas após scoring heurístico e
para vagas candidatas (score >= threshold).
Valida JSON contra schema - saída livre do LLM nunca controla pipeline diretamente.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema de saída validado (spec seção 8)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "Você é um classificador de vagas para um candidato Júnior/Estágio em "
    "MLOps, Engenharia de Software, Dados e Ciência de Dados. "
    "Avalie a vaga com rigor e retorne APENAS JSON válido no schema "
    "especificado, sem markdown, sem explicação extra. "
    "Seja conservador: só dê overall_match alto se houver forte aderência "
    "técnica e senioridade compatível."
)


def _build_user_prompt(job: dict[str, Any]) -> str:
    keys = (
        "relevance_score, seniority_match, area_match, technology_match, "
        "remote_match, overall_match, recommendation, reason, "
        "missing_requirements, matching_skills, concerns"
    )
    example = (
        '{"relevance_score": 85, "seniority_match": 90, "area_match": 80, '
        '"technology_match": 85, "remote_match": 100, "overall_match": 87, '
        '"recommendation": "apply", "reason": "...", '
        '"missing_requirements": [], "matching_skills": ["Python"], '
        '"concerns": []}'
    )
    return (
        f"Classifique esta vaga. Retorne JSON com as chaves exatas: {keys}.\n\n"
        f"Vaga:\n"
        f"- título: {job.get('title')}\n"
        f"- empresa: {job.get('company')}\n"
        f"- localização: {job.get('location')}\n"
        f"- modalidade: {job.get('modality')}\n"
        f"- senioridade: {job.get('seniority')}\n"
        f"- descrição: {(job.get('description') or '')[:4000]}\n"
        f"- requisitos: {job.get('requirements') or job.get('description') or ''[:2000]}\n"
        f"- tecnologias: {job.get('technologies')}\n"
        f"- URL: {job.get('url')}\n\n"
        f"Responda apenas com JSON. Exemplo:\n{example}\n"
    )


class LLMClassification(BaseModel):
    """Schema validado da saída do LLM (spec seção 8)."""

    relevance_score: int = Field(ge=0, le=100)
    seniority_match: int = Field(ge=0, le=100)
    area_match: int = Field(ge=0, le=100)
    technology_match: int = Field(ge=0, le=100)
    remote_match: int = Field(ge=0, le=100)
    overall_match: int = Field(ge=0, le=100)
    recommendation: str = Field(pattern="^(apply|consider|ignore)$")
    reason: str
    missing_requirements: list[str] = Field(default_factory=list)
    matching_skills: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class BaseLLMProvider(ABC):
    @abstractmethod
    def is_enabled(self) -> bool: ...

    @abstractmethod
    def classify(self, job: dict[str, Any]) -> LLMClassification | None:
        """Classifica vaga; retorna None se LLM desabilitado ou erro recuperável."""
        ...


# ---------------------------------------------------------------------------
# Ollama Provider - http://localhost:11434  (ou serviço docker 'ollama')
# ---------------------------------------------------------------------------


class OllamaProvider(BaseLLMProvider):
    """Provider Ollama - local (sem custo) ou cloud (https://ollama.com, free tier).

    Gratuito: local roda 100% offline; cloud usa free tier em https://ollama.com (light usage,
    modelos *-cloud como gpt-oss:20b-cloud). Basta setar OLLAMA_BASE_URL=https://ollama.com
    e OLLAMA_API_KEY.
    """

    def __init__(self, base_url: str, model: str, timeout: int = 60, api_key: str | None = None):
        # Pega direto do .env sem sanitização - usuário controla URL completa
        self.base_url = base_url.strip().rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = api_key

    def is_enabled(self) -> bool:
        return bool(self.base_url and self.model)

    def classify(self, job: dict[str, Any]) -> LLMClassification | None:
        prompt = _build_user_prompt(job)
        # payloads separados: Ollama nativo vs OpenAI compatível
        ollama_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 800},
        }
        openai_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        # determina URLs e payloads a tentar - corrige http->https para cloud
        base = self.base_url
        # Ollama Cloud http -> 405/301 se POST redirecionado, usa https direto
        if base.startswith("http://ollama.com"):
            base = base.replace("http://", "https://")
        if base.endswith(("/api/chat", "/v1/chat/completions")):
            # se usuário já deu URL completa, tenta as duas variantes a partir do host
            host = base.replace("/api/chat", "").replace("/v1/chat/completions", "").rstrip("/")
            urls = [
                (f"{host}/api/chat", ollama_payload),
                (f"{host}/v1/chat/completions", openai_payload),
            ]
            # prioriza a URL exata que o usuário configurou
            if base.endswith("/api/chat"):
                urls = [(base.replace("http://", "https://") if base.startswith("http://ollama.com") else base, ollama_payload)] + [u for u in urls if u[0] != base]
            else:
                urls = [(base.replace("http://", "https://") if base.startswith("http://ollama.com") else base, openai_payload)] + [u for u in urls if u[0] != base]
        else:
            urls = [
                (f"{base}/v1/chat/completions", openai_payload),
                (f"{base}/api/chat", ollama_payload),
            ]
        last_err: Exception | None = None
        for url, pl in urls:
            try:
                resp = self._call(url, pl)
                if resp:
                    return resp
            except Exception as e:
                last_err = e
                logger.debug("Ollama tentativa falhou url=%s err=%s", url, e)
                continue
        if last_err:
            logger.warning("Ollama classify falhou model=%s err=%s", self.model, last_err)
        return None

    def _call(self, url: str, payload: dict) -> LLMClassification | None:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        # Cloud http -> https 301 precisa follow_redirects
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            r = client.post(url, json=payload, headers=headers or None)
            r.raise_for_status()
            data = r.json()

        # Extrai conteúdo conforme formato da resposta
        content: str | None = None
        if "choices" in data:  # OpenAI compatível
            content = data["choices"][0]["message"]["content"]
        elif "message" in data:  # Ollama nativo /api/chat
            content = data["message"]["content"]
        elif "response" in data:  # Ollama /api/generate
            content = data["response"]

        if not content:
            logger.warning("Ollama resposta sem conteúdo: %s", data)
            return None
        return _parse_and_validate(content)

    def health_check(self) -> bool:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        # usa exatamente a base da .env (sem sanitização) - tenta /api/tags relativo
        # se base já é .../api/chat, troca sufixo por /api/tags
        base = self.base_url
        if base.endswith("/api/chat"):
            check_base = base[: -len("/api/chat")]
        elif base.endswith("/v1/chat/completions"):
            check_base = base[: -len("/v1/chat/completions")]
        else:
            check_base = base
        try:
            with httpx.Client(timeout=5, follow_redirects=True) as client:
                r = client.get(f"{check_base}/api/tags", headers=headers or None)
                # Ollama Cloud http -> 301 para https, ollama local 200
                return r.status_code in (200, 301, 302)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str | None = None, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def classify(self, job: dict[str, Any]) -> LLMClassification | None:
        prompt = _build_user_prompt(job)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
            content = data["choices"][0]["message"]["content"]
            return _parse_and_validate(content)
        except Exception as e:
            logger.warning("OpenAI classify falhou model=%s err=%s", self.model, e)
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_and_validate(content: str) -> LLMClassification | None:
    """Extrai JSON da resposta (remove markdown fences se houver) e valida."""
    text = content.strip()
    # Remove ```json ... ``` se o modelo devolver markdown
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("LLM retornou JSON inválido: %s | raw=%.500s", e, text)
        return None
    try:
        return LLMClassification.model_validate(data)
    except ValidationError as e:
        logger.warning("LLM JSON não passou no schema: %s | data=%s", e, data)
        return None


class DisabledProvider(BaseLLMProvider):
    def is_enabled(self) -> bool:
        return False

    def classify(self, job: dict[str, Any]) -> LLMClassification | None:
        return None


def get_llm_provider() -> BaseLLMProvider:
    """Factory baseada em settings.llm_provider.

    - ollama  -> OllamaProvider
    - openai  -> OpenAIProvider
    - auto    -> tenta Ollama se responder, senão OpenAI se tiver key
    - disabled -> nunca chama LLM
    """
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if not settings.llm_enabled or provider == "disabled":
        return DisabledProvider()

    if provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_timeout,
            settings.ollama_api_key,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning("llm_provider=openai mas OPENAI_API_KEY não configurada")
            return DisabledProvider()
        return OpenAIProvider(
            settings.openai_api_key, settings.openai_model, settings.openai_base_url
        )

    # auto
    if provider == "auto":
        # Prefere Ollama (local ou cloud) se health check ok, senão OpenAI
        ollama = OllamaProvider(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_timeout,
            settings.ollama_api_key,
        )
        try:
            ok = ollama.health_check()
        except Exception as e:
            logger.debug("Ollama health_check exceção: %s", e)
            ok = False
        if ok:
            logger.info(
                "LLM auto: usando Ollama %s @ %s",
                settings.ollama_model,
                settings.ollama_base_url,
            )
            return ollama
        # fallback OpenAI mesmo que Ollama configurado mas offline
        if settings.openai_api_key:
            # mascarar key no log
            key_hint = settings.openai_api_key[:7] + "..." if len(settings.openai_api_key) > 7 else "***"
            logger.info("LLM auto: Ollama offline (%s), usando OpenAI %s key=%s", settings.ollama_base_url, settings.openai_model, key_hint)
            return OpenAIProvider(
                settings.openai_api_key, settings.openai_model, settings.openai_base_url
            )
        logger.warning("LLM auto: nenhum provider disponível (Ollama %s offline e OPENAI_API_KEY vazia) -> disabled. Configure LLM_PROVIDER=openai ou OLLAMA_BASE_URL", settings.ollama_base_url)
        return DisabledProvider()

    logger.warning("llm_provider desconhecido '%s' -> disabled", provider)
    return DisabledProvider()
