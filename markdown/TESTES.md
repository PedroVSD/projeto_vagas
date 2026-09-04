# Guia de Testes — Job Finder (Agente de Vagas)

Instruções completas para testar o projeto localmente, com e sem Docker.

---

## Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Setup Inicial](#2-setup-inicial)
3. [Testes Automatizados (pytest)](#3-testes-automatizados-pytest)
4. [Testes por Módulo](#4-testes-por-módulo)
5. [Lint e Qualidade](#5-lint-e-qualidade)
6. [Testes Manuais via API](#6-testes-manuais-via-api)
7. [Testes com Docker](#7-testes-com-docker)
8. [Testes de Integração com Banco](#8-testes-de-integração-com-banco)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Pré-requisitos

| Ferramenta | Versão mínima | Verificação |
|---|---|---|
| Python | 3.11+ | `python --version` |
| uv | última | `uv --version` — instale em https://docs.astral.sh/uv/ |
| Docker + Compose | última | `docker --version && docker compose version` |
| PostgreSQL | 16 (se rodar sem Docker) | `psql --version` |

---

## 2. Setup Inicial

### 2.1 Clonar e configurar env

```bash
cp .env.example .env
# edite .env se precisar (DATABASE_URL, tokens Telegram/Email, LLM)
```

`.env` mínimo para testes automatizados (sem credenciais externas):

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/job_finder
LLM_PROVIDER=disabled
TELEGRAM_BOT_TOKEN=
SMTP_HOST=
```

> Os 49 testes atuais **não exigem** banco, Telegram, Email ou LLM reais — usam mocks. Só precisam de `.env` existente.

### 2.2 Instalar dependências

```bash
# com uv (recomendado)
uv sync

# verifica instalação
uv run python --version
uv run pytest --version
```

### 2.3 Banco (opcional — só para testes manuais/integração)

```bash
# via Docker (recomendado)
docker compose up -d db

# ou Postgres local já rodando:
# ajuste DATABASE_URL no .env para apontar para seu Postgres local

# aplicar migrations
uv run alembic upgrade head

# verificar
uv run alembic current
```

---

## 3. Testes Automatizados (pytest)

Suite atual: **49 testes** em `tests/` — todos isolados com mocks, sem depender de APIs externas.

### 3.1 Rodar todos os testes

```bash
uv run pytest
# saída esperada: 49 passed
```

### 3.2 Modo verboso

```bash
uv run pytest -v
```

### 3.3 Teste específico

```bash
# um arquivo
uv run pytest tests/test_scoring.py -v

# uma função
uv run pytest tests/test_scoring.py::test_junior_data_engineer_excelente -v

# por palavra-chave
uv run pytest -k "llm or scoring" -v
```

### 3.4 Com cobertura (requer pytest-cov)

```bash
# instalar se ainda não tem
uv add --dev pytest-cov  # ou uv sync --group dev se já está em pyproject.toml

# rodar
uv run pytest --cov=app --cov-report=term-missing
uv run pytest --cov=app --cov-report=html  # gera htmlcov/index.html
```

> Nota: `pyproject.toml:22` lista `dev` com `pytest`, `pytest-asyncio`, `ruff` mas **não inclui** `pytest-cov` por padrão. Adicione se quiser relatório de cobertura.

### 3.5 Opções úteis

```bash
uv run pytest -q                  # silencioso (só sumário)
uv run pytest --tb=short          # traceback curto
uv run pytest --collect-only -q   # lista os 49 testes sem executar
uv run pytest -x                  # para no primeiro erro
uv run pytest --lf                # re-executa só quem falhou antes
```

---

## 4. Testes por Módulo

| Arquivo | O que testa | Comando |
|---|---|---|
| `test_health.py` | `GET /` e `GET /health` | `uv run pytest tests/test_health.py -v` |
| `test_jobs_api.py` | OpenAPI e docs | `uv run pytest tests/test_jobs_api.py -v` |
| `test_normalization.py` | `extract_technologies`, `extract_seniority`, `extract_modality` | `uv run pytest tests/test_normalization.py -v` |
| `test_deduplication.py` | fingerprint estável, case/acento insensitive | `uv run pytest tests/test_deduplication.py -v` |
| `test_scoring.py` | scoring 0-100, cap de techs, classificação, `is_relevant` | `uv run pytest tests/test_scoring.py -v` |
| `test_sources.py` | `DemoSource`, `Arbeitnow` (mock), registry, dedup | `uv run pytest tests/test_sources.py -v` |
| `test_queries.py` | `config/search_queries.yaml` (21 queries) | `uv run pytest tests/test_queries.py -v` |
| `test_notifications.py` | `format_job_message`, thresholds, Telegram/Email mock | `uv run pytest tests/test_notifications.py -v` |
| `test_workers.py` | pipeline `runner`, digest, `GET /worker/status`, `POST /worker/run` | `uv run pytest tests/test_workers.py -v` |
| `test_llm.py` | parse JSON LLM, `OllamaProvider` mock, `score_and_persist` | `uv run pytest tests/test_llm.py -v` |
| `test_observability.py` | `GET /metrics`, `GET /observability`, `GET /health/detailed` | `uv run pytest tests/test_observability.py -v` |

Exemplo de saída esperada (`test_scoring.py`):

```
tests/test_scoring.py::test_junior_data_engineer_excelente PASSED
tests/test_scoring.py::test_estagio_mlops_muito_relevante PASSED
tests/test_scoring.py::test_senior_ignorar PASSED
tests/test_scoring.py::test_tech_cap PASSED
```

---

## 5. Lint e Qualidade

```bash
# ruff check (definido em pyproject.toml:29 — E, F, I, UP, line-length 100)
uv run ruff check .

# auto-fix
uv run ruff check --fix .

# format (se habilitado)
uv run ruff format .
```

---

## 6. Testes Manuais via API

### 6.1 Subir a API

**Sem Docker:**

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# API em http://localhost:8000  |  docs em http://localhost:8000/docs
```

**Com Docker:**

```bash
docker compose up --build
# aguarda "Application startup complete"
```

### 6.2 Endpoints básicos (curl)

```bash
# health
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed
curl http://localhost:8000/health/db

# root
curl http://localhost:8000/

# métricas / observabilidade
curl http://localhost:8000/metrics
curl http://localhost:8000/observability

# openapi
curl http://localhost:8000/openapi.json | head -n 50
```

### 6.3 Jobs

```bash
# lista (vazia se nunca ingeriu)
curl "http://localhost:8000/jobs?limit=10"

# recomendadas (score >= threshold)
curl http://localhost:8000/jobs/recommended

# busca textual
curl "http://localhost:8000/jobs/search/text?q=python"

# detalhe
curl http://localhost:8000/jobs/1
```

### 6.4 Sources / Ingestão

```bash
# lista fontes disponíveis
curl http://localhost:8000/sources

# lista queries (21)
curl http://localhost:8000/sources/queries

# preview sem persistir (scoring incluído)
curl http://localhost:8000/sources/preview/demo
curl http://localhost:8000/sources/preview/arbeitnow

# ingestão completa (coleta + scoring + notificação)
curl -X POST http://localhost:8000/sources/ingest

# recomputa score de um job
curl -X POST http://localhost:8000/scoring/recompute/1
```

### 6.5 Worker / Scheduler

```bash
curl http://localhost:8000/worker/status
curl -X POST http://localhost:8000/worker/run
```

### 6.6 Notificações

```bash
curl http://localhost:8000/notifications
curl http://localhost:8000/notifications/digest
curl http://localhost:8000/notifications/providers

# teste de envio (requer TELEGRAM_BOT_TOKEN ou SMTP configurado)
curl -X POST http://localhost:8000/notifications/test
```

### 6.7 LLM

```bash
curl http://localhost:8000/scoring/llm/status

curl -X POST http://localhost:8000/scoring/llm/classify \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Junior MLOps Engineer",
    "company": "Empresa X",
    "location": "Remoto - Brasil",
    "description": "Vaga Python Docker Kubernetes para júnior",
    "technologies": ["Python", "Docker"]
  }'
```

### 6.8 Swagger / ReDoc

Abra no navegador:

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Use "Try it out" para testar qualquer endpoint sem curl.

---

## 7. Testes com Docker

### 7.1 API + DB (mínimo)

```bash
docker compose up --build
# testa
curl http://localhost:8000/health
curl http://localhost:8000/metrics
docker compose down
```

### 7.2 Com Worker/Scheduler

```bash
docker compose --profile worker up --build
docker compose --profile worker logs -f worker

# em outro terminal
curl http://localhost:8000/worker/status
curl -X POST http://localhost:8000/worker/run
```

### 7.3 Com Ollama local (LLM grátis)

```bash
docker compose --profile ollama up -d
docker exec projeto_vagas-ollama-1 ollama pull llama3.1:8b

# no .env:
# OLLAMA_BASE_URL=http://ollama:11434
# OLLAMA_MODEL=llama3.1:8b
# LLM_PROVIDER=ollama

curl http://localhost:8000/scoring/llm/status
```

### 7.4 Testes automatizados dentro do container

```bash
docker compose exec api uv run pytest -v
docker compose exec api uv run pytest --collect-only -q
docker compose exec api uv run ruff check .
```

### 7.5 Limpeza

```bash
docker compose down -v   # remove volumes (pgdata, ollama_data)
docker compose down      # mantém dados
```

---

## 8. Testes de Integração com Banco

Para validar persistência real (não mockada):

```bash
# 1. subir db
docker compose up -d db

# 2. migrations
uv run alembic upgrade head

# 3. ingestão real (bate na API Arbeitnow)
curl -X POST http://localhost:8000/sources/ingest

# 4. verificar no banco
docker compose exec db psql -U postgres -d job_finder -c "SELECT id, title, company_id, fingerprint FROM job LIMIT 5;"
docker compose exec db psql -U postgres -d job_finder -c "SELECT job_id, heuristic_score, final_score, classification FROM job_score LIMIT 5;"
docker compose exec db psql -U postgres -d job_finder -c "SELECT * FROM notification LIMIT 5;"

# 5. health com DB
curl http://localhost:8000/health/db
curl http://localhost:8000/health/detailed

# 6. rollback se precisar
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

## 9. Troubleshooting

| Problema | Causa | Solução |
|---|---|---|
| `connection refused` no pytest com DB | DB não subiu | `docker compose up -d db` + `uv run alembic upgrade head` |
| `48 passed, 1 failed` | env faltando | `cp .env.example .env` e rode de novo |
| `ModuleNotFoundError: app` | fora do venv | use sempre `uv run pytest` (não `pytest` direto) |
| `alembic: command not found` | sem uv | `uv run alembic ...` |
| `TELEGRAM_BOT_TOKEN not set` | provider desabilitado | esperado se sem token — teste `test_telegram_disabled_without_config` valida isso |
| `OLLAMA timeout` | Ollama não rodando | `LLM_PROVIDER=disabled` no `.env` para testes locais sem LLM |
| Porta 8000/5432 em uso | conflito | `lsof -i :8000` / `docker compose down` |
| `ruff` não encontrado | dev deps não instaladas | `uv sync --group dev` |

### Logs úteis

```bash
# app local
LOG_LEVEL=DEBUG uv run uvicorn app.main:app --reload

# docker
docker compose logs -f api
docker compose logs -f db
docker compose logs -f worker

# métricas do runner (últimas 100 execuções)
curl http://localhost:8000/observability | python -m json.tool
```

---

## Resumo rápido (copy-paste)

```bash
# 1. setup
cp .env.example .env
uv sync

# 2. testes (49, sem precisar de DB/LLM/Telegram)
uv run pytest -v

# 3. lint
uv run ruff check .

# 4. API manual (com DB)
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# em outro terminal:
curl http://localhost:8000/health
curl -X POST http://localhost:8000/sources/ingest
curl http://localhost:8000/jobs/recommended
curl http://localhost:8000/metrics

# 5. tudo via Docker
docker compose up --build
```

---

*Gerado para `job-finder` v0.1.0 — `pyproject.toml:1`, `app/main.py:20`, `tests/` com 49 testes.*
