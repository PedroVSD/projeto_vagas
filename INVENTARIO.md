# Inventário - projeto_vagas (job-finder 0.1.0)

> Gerado em 2026-08-25. Fonte principal: `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `Dockerfile`, `alembic.ini`

## 1. Gerenciador / Build

- **Python `>=3.11`** (`pyproject.toml:6`) — Docker usa `python:3.12-slim` (`Dockerfile:1`)
- **uv** (`uv.lock:1`, `Dockerfile:6` `ghcr.io/astral-sh/uv:latest`) — `uv sync` (`Dockerfile:24`)
- **hatchling** build-backend (`pyproject.toml:47`)
- **Ambiente**: `.venv/` (123M) dentro do projeto, instalação `editable` (`job-finder 0.1.0 /projeto_vagas`)

## 2. Dependências de Produção (`pyproject.toml:7`)

| Pacote | Versão (lock) | Uso no projeto |
|---|---|---|
| `fastapi` | `0.141.1` | API REST (`app/main.py:3`, `app/api/routes/*`) |
| `uvicorn[standard]` | `0.52.4` | Servidor ASGI. Extras: `httptools 0.8.0`, `uvloop 0.22.1`, `watchfiles 1.2.0`, `websockets 17.0.1` |
| `sqlalchemy` | `2.0.52` | ORM (`app/models/*`, `app/core/database.py`) |
| `alembic` | `1.19.1` | Migrations (`alembic.ini:3`, `migrations/`) |
| `psycopg[binary]` | `3.3.4` | Driver Postgres |
| `pydantic` + `pydantic-core` | `2.13.4` / `2.46.4` | Schemas (`app/schemas/*`) |
| `pydantic-settings` | `2.15.0` | Config (`app/core/config.py`) |
| `python-dotenv` | `1.2.3` | `.env` |
| `httpx` | `0.28.1` | Cliente HTTP (`app/sources/*`, `app/notifications/*`) |
| `pyyaml` | `6.0.3` | `config/search_queries.yaml` |
| `apscheduler` | `3.11.3` | Agendamento (`app/workers/scheduler.py`) |

**Transitivas**: `starlette 1.6.0`, `anyio 4.14.2`, `h11 0.16.0`, `httpcore 1.0.9`, `greenlet 3.5.5`, `mako 1.4.1`, `markupsafe 3.0.3`, `tzlocal 5.4.4`, `certifi`, `idna`, `typing-extensions`, `annotated-types`, `click`.

## 3. Dependências de Desenvolvimento (`pyproject.toml:21` grupo `dev`)

- `pytest 9.1.1` + `pytest-asyncio 1.4.0` (`pyproject.toml:36` `testpaths = ["tests"]`)
- `ruff 0.16.4` — linter `E,F,I,UP`, `line-length 100`, `py311` (`pyproject.toml:29`)
- `httpx` (reuso em testes)

## 4. Infraestrutura (`docker-compose.yml`, `Dockerfile`)

| Serviço | Imagem | Porta | Volume / Profile |
|---|---|---|---|
| `db` | `postgres:16-alpine` (`docker-compose.yml:3`) | `5432:5432` | `pgdata:/var/lib/postgresql/data` |
| `api` | `build: .` (`Dockerfile:1`) | `8000:8000` | `alembic upgrade head && uvicorn --reload` |
| `worker` | `build: .` | — | profile `worker`, `python -m app.workers.scheduler` |
| `scheduler` | `build: .` | — | profile `scheduler` (alias) |
| `redis` | `redis:7-alpine` (`docker-compose.yml:87`) | `6379:6379` | profiles `worker`,`celery` |
| `ollama` | `ollama/ollama:latest` (`docker-compose.yml:97`) | `11434:11434` | profile `ollama`, `ollama_data:/root/.ollama` |

Deps sistema no Docker: `libpq5`, `curl` (`Dockerfile:13`).

## 5. O que está empacotado na pasta do projeto?

### Dentro da pasta (portável, mas nem tudo versionado)

- Código fonte: `app/`, `migrations/`, `config/`, `pyproject.toml`, `uv.lock`, `Dockerfile`, `alembic.ini`
- `.venv/` (123M) — fisicamente dentro, mas **ignorado** no git (`.gitignore:6` `.venv/`, `.gitignore:9` `.venv*/`)

### Fora da pasta (não empacotado)

- Cache global `uv` em `~/.cache/uv` (3.1G)
- Volumes Docker: `projeto_vagas_pgdata` (`pgdata:/var/lib/postgresql/data` em `docker-compose.yml:12`, ignorado em `.gitignore:35`)
- Imagens Docker (baixadas pelo daemon, não na pasta)
- `.env` (`.gitignore:8` `env_file` em `docker-compose.yml:32`)

> Recriável 100% via `uv sync` + `docker compose up`, mas não autocontido sem `.venv` e volumes externos.
