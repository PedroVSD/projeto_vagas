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
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = api_key

    def is_enabled(self) -> bool:
        return bool(self.base_url and self.model)

    def classify(self, job: dict[str, Any]) -> LLMClassification | None:
        prompt = _build_user_prompt(job)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 800},
        }
        # Tenta endpoint OpenAI-compatível primeiro,
        # fallback para /api/chat nativo
        urls = [
            f"{self.base_url}/v1/chat/completions",
            f"{self.base_url}/api/chat",
        ]
        last_err: Exception | None = None
        for url in urls:
            try:
                resp = self._call(url, payload)
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
        # Adapta payload entre formato OpenAI e Ollama nativo (são quase idênticos para chat)
        with httpx.Client(timeout=self.timeout) as client:
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
        try:
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            # Cloud usa https://ollama.com/api/tags (mesmo endpoint)
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{self.base_url}/api/tags", headers=headers or None)
                return r.status_code == 200
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
        if ollama.health_check():
            logger.info(
                "LLM auto: usando Ollama %s @ %s",
                settings.ollama_model,
                settings.ollama_base_url,
            )
            return ollama
        if settings.openai_api_key:
            logger.info("LLM auto: Ollama indisponível, usando OpenAI %s", settings.openai_model)
            return OpenAIProvider(
                settings.openai_api_key, settings.openai_model, settings.openai_base_url
            )
        logger.info("LLM auto: nenhum provider disponível (Ollama offline e sem key) -> disabled")
        return DisabledProvider()

    logger.warning("llm_provider desconhecido '%s' -> disabled", provider)
    return DisabledProvider()
