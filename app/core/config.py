from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = Field(default="job-finder")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    api_port: int = Field(default=8000)

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/job_finder"
    )

    # Redis (opcional, para Fase 5 - Celery)
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Scoring
    score_threshold: int = Field(default=60, ge=0, le=100)
    immediate_threshold: int = Field(default=90, ge=0, le=100)

    # Notificações - Telegram
    telegram_bot_token: str | None = Field(default=None)
    telegram_chat_id: str | None = Field(default=None)

    # Notificações - Email
    smtp_host: str | None = Field(default=None)
    smtp_port: int | None = Field(default=None)
    smtp_username: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_from: str | None = Field(default=None)
    smtp_to: str | None = Field(default=None)

    # LLM - provider: "ollama" | "openai" | "auto" | "disabled"
    llm_provider: str = Field(default="auto", description="ollama, openai, auto, disabled")
    llm_enabled: bool = Field(default=True)

    # Ollama - local (http://localhost:11434) ou cloud (https://ollama.com)
    # Cloud gratuito: crie conta em https://ollama.com,
    # gere API key em https://ollama.com/settings/keys e use
    # OLLAMA_BASE_URL=https://ollama.com + OLLAMA_API_KEY +
    # modelo cloud (ex: gpt-oss:20b-cloud, qwen3-coder:480b-cloud)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1:8b")
    ollama_api_key: str | None = Field(
        default=None, description="API key para Ollama Cloud (https://ollama.com)"
    )
    ollama_timeout: int = Field(default=60)

    # OpenAI
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")
    openai_base_url: str | None = Field(default=None)

    # Digest
    digest_enabled: bool = Field(default=True)
    digest_time: str = Field(default="08:00")

    # Scheduler (Fase 5) - APScheduler simples, monólito modular
    scheduler_enabled: bool = Field(default=True)
    scheduler_interval_minutes: int = Field(
        default=60, ge=1, description="Intervalo coleta em minutos"
    )
    scheduler_collect_on_start: bool = Field(default=False, description="Executa coleta ao iniciar")

    # Display - data/hora brasileira (config/search_queries.yaml display)
    display_timezone: str = Field(
        default="America/Sao_Paulo", description="IANA timezone p/ notificações"
    )
    display_date_format: str = Field(
        default="%d/%m/%Y às %H:%M", description="strftime p/ Data encontrada"
    )
    display_locale: str = Field(default="pt_BR")

    # Throttling - yaml config/search_queries.yaml throttling tem prioridade sobre env
    llm_throttle_seconds: int = Field(
        default=300, ge=0, description="Segundos entre chamadas LLM (yaml throttling.llm_throttle_seconds tem prioridade)"
    )
    telegram_throttle_seconds: int = Field(
        default=60, ge=0, description="Segundos entre mensagens Telegram (yaml throttling.telegram_throttle_seconds tem prioridade)"
    )

    # Observabilidade (Fase 7)
    log_format: str = Field(default="text", description="text ou json")


@lru_cache
def get_settings() -> Settings:
    return Settings()
