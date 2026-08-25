# Agente de Busca Automatizada de Vagas

> Sistema automatizado de coleta, filtragem, ranqueamento e notificação de vagas de emprego relevantes — focado em Estágio/Júnior/Entry-level nas áreas de MLOps, Engenharia de Software, Engenharia de Dados e Ciência de Dados.

Pipeline contínuo que roda em intervalos regulares, determina relevância real para o perfil e notifica apenas as melhores oportunidades.

```
[Scheduler] → [Job Sources] → [Normalização] → [Deduplicação] → [Filtragem Heurística] → [Scoring 0-100] → [LLM Classification - opcional] → [PostgreSQL] → [Notification Service] → [Email / Telegram / WhatsApp]
```

---

## Índice

- [Perfil Alvo](#perfil-alvo)
- [Arquitetura](#arquitetura)
- [Decisões Tecnológicas](#decisões-tecnológicas)
- [Modelo de Dados](#modelo-de-dados)
- [Fluxo Completo](#fluxo-completo)
- [Estratégia de Scoring](#estratégia-de-scoring)
- [Estratégia de Coleta](#estratégia-de-coleta)
- [Estratégia de Notificações](#estratégia-de-notificações)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Configuração](#configuração)
- [Como Executar Localmente](#como-executar-localmente)
- [API](#api)
- [Observabilidade](#observabilidade)
- [Testes](#testes)
- [Plano de Implementação por Etapas](#plano-de-implementação-por-etapas)
- [Deploy](#deploy)
- [Segurança e Compliance](#segurança-e-compliance)

---

## Perfil Alvo

**Senioridade:** Estágio, Júnior, Entry-level, Trainee com aderência técnica.

**Áreas prioritárias:**

1. MLOps
2. Engenharia de Software
3. Engenharia de Dados
4. Ciência de Dados

**Áreas secundárias (com boa aderência):** Machine Learning Engineer, Data Engineer, Backend Engineer, Python Developer, AI Engineer, Platform Engineer, DevOps/Cloud (com relação ML/data), Analytics Engineer, NLP Engineer, AI/ML Intern, Research/Applied ML Intern.

**Stack de interesse (usada para medir aderência, não como requisito obrigatório):** Python, Go/Golang, SQL, Docker, Kubernetes, FastAPI, Git/GitHub, Linux, AWS/GCP/Azure, Airflow, Spark/PySpark, Databricks, MLflow, CI/CD, REST, PostgreSQL, Redis, Kafka, ML, NLP, LLMs.

**Localização (ordem de prioridade):** 1. Remoto → 2. Remoto no Brasil → 3. Híbrido no Brasil → 4. Presencial (somente se excepcionalmente relevante). Vagas internacionais remotas com contratação no Brasil recebem pontuação alta.

---

## Arquitetura

Monólito modular (evolui para serviços separados apenas quando houver necessidade real).

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  Scheduler  │────▶│ Job Sources  │────▶│ Normalização │────▶│Deduplicação │
│ (APScheduler│     │ (adapters)   │     │              │     │(fingerprint)│
│  /Celery)   │     └──────────────┘     └──────────────┘     └──────┬──────┘
└─────────────┘                                                      │
                                                                     ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│Notificação  │◀────│ PostgreSQL   │◀────│ LLM (opcional)│◀───│Scoring 0-100│
│(adapters)   │     │              │     │ classificação │    │ + Filtragem │
└──────┬──────┘     └──────┬───────┘     └──────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
 Email/Telegram      API FastAPI
 WhatsApp/Discord
 Slack (futuro)
```

**Princípios:** simplicidade, modularidade, baixo custo, fácil manutenção, sem scraping agressivo.

### Componentes

| Componente | Responsabilidade |
|---|---|
| **Collector Worker** | Busca vagas em todas as fontes configuradas |
| **Scoring Worker** | Aplica filtros determinísticos + scoring heurístico + LLM opcional |
| **Notification Worker** | Envia notificações individuais e digest diário |
| **API (FastAPI)** | Consulta de vagas, preferências, fontes, notificações |
| **Scheduler** | Orquestra execução periódica do pipeline |
| **PostgreSQL** | Persistência com histórico de scores/notificações |
| **Redis** *(opcional)* | Fila/cache se usar Celery |

---

## Decisões Tecnológicas

| Decisão | Escolha | Justificativa |
|---|---|---|
| **API** | FastAPI + Pydantic + SQLAlchemy + Alembic | Performance, validação automática, async, ecossistema maduro, tipagem |
| **Banco** | PostgreSQL | Índices, JSONB, robustez, suporte a fingerprints/FTS |
| **Gerenciador Python** | `uv` | Substituto rápido para pip/poetry, lockfile determinístico |
| **Scheduler** | APScheduler (Fase 1-5) → Celery+Redis se escalar | APScheduler é mais simples para MVP/monólito; Celery quando precisar de workers distribuídos e retry robusto |
| **Fila** | In-process / APScheduler → Redis + Celery | Evitar complexidade prematura |
| **Container** | Docker + Docker Compose | Reprodutibilidade local com `docker compose up` |
| **LLM** | Ollama (local grátis ou Cloud free tier via https://ollama.com) + OpenAI opcional, JSON schema validado | Custo controlado: Ollama local 100% grátis/offline, Ollama Cloud free tier (light usage, modelos `*-cloud` sem GPU local), só após filtro heurístico (score >= threshold) |
| **Notificações** | Adapter pattern (`NotificationProvider.send()`) | Desacoplamento: Email/Telegram agora, WhatsApp/Discord/Slack futuros sem alterar negócio |
| **Coleta** | Adapter pattern (`JobSource.fetch_jobs() / normalize_job()`) | Fontes plugáveis sem tocar pipeline |

---

## Modelo de Dados

```sql
-- Entidades principais
Job(id, fingerprint UNIQUE, title, company_id, source_id, url UNIQUE,
    description, location, modality, seniority, technologies TEXT[],
    raw_payload JSONB, first_seen_at, last_seen_at, updated_at)

Company(id, name UNIQUE, website, created_at)

JobSource(id, name UNIQUE, enabled, config JSONB, last_run_at)

JobScore(job_id FK, heuristic_score, llm_score, final_score,
         seniority_breakdown JSONB, area_breakdown JSONB,
         tech_breakdown JSONB, modality_breakdown JSONB,
         penalties JSONB, classification, created_at)

Notification(id, job_id FK, provider, channel, payload JSONB,
             sent_at, status)

SearchQuery(id, query_text, family, enabled, source_filter, created_at)

UserPreference(id, min_score_threshold, notify_channels TEXT[],
               digest_enabled, digest_time, immediate_threshold, updated_at)
```

**Índices:** `fingerprint`, `url`, `(company_id, title)`, `final_score`, `first_seen_at`, `modality`, `seniority`, GIN em `technologies` e `raw_payload`.

**Fingerprint estável:** `hash(company + normalized_title + location + url + description_hash)` — consolida mesma vaga de múltiplas fontes em registro único e evita re-notificação.

---

## Fluxo Completo

1. **Scheduler** dispara pipeline (ex: a cada 30-60 min).
2. **Coleta:** cada `JobSource` executa `fetch_jobs()` com suas queries configuradas (busca apenas vagas novas desde `last_run_at`).
3. **Normalização:** `normalize_job()` padroniza campos (título, empresa, localização, modalidade, senioridade, tecnologias, URL, descrição).
4. **Deduplicação:** calcula fingerprint; se já existe, atualiza `last_seen_at`/`description`; senão insere.
5. **Filtragem heurística:** descarta vagas sem relação com software/dados/ML ou com penalidades bloqueantes.
6. **Scoring 0-100:** soma pontos por senioridade/área/modalidade/tecnologias, aplica penalidades e cap por categoria.
7. **LLM (opcional, custo-controlado):** apenas para vagas candidatas (ex: score >= 60); valida JSON contra schema; não controla pipeline diretamente.
8. **Persistência:** salva `Job` + `JobScore` no PostgreSQL.
9. **Notificação:** se `final_score >= threshold` (default 60) e nunca notificada → envia via adapters configurados; `>= 90` pode ser imediato, demais vão no digest diário 08:00.
10. **Observabilidade:** registra métricas por execução (coletadas, novas, duplicadas, descartadas, enviadas, erros por fonte, tempo).

---

## Estratégia de Scoring

Score final 0-100 com cap por categoria para evitar inflação por keyword stuffing.

| Dimensão | Regra | Pontos |
|---|---|---|
| **Senioridade** | Estágio/Internship | +25 |
| | Júnior | +25 |
| | Entry-level | +20 |
| | Trainee | +15 |
| | Pleno | -20 |
| | Sênior | -50 |
| | Staff/Principal/Lead | -80 |
| **Área** | MLOps / MLE / Data Eng. | +25 |
| | Software Eng. / Data Science / AI Eng. | +20 |
| | Backend / DevOps/Platform / Analytics Eng. | +15 |
| | Data Analyst | +5 |
| **Modalidade** | Remoto no Brasil | +25 |
| | Remoto | +20 |
| | Híbrido | +5 |
| | Presencial | -10 |
| **Tecnologias** | Python, Go, Docker, K8s, Airflow, Spark, Databricks, MLflow, ML, NLP, LLM | +5 cada (cap ~25) |
| | AWS, GCP, FastAPI, SQL, Kafka, CI/CD | +4 cada |
| | Azure, PostgreSQL | +3 cada |
| **Penalidades** | Exige 5+ anos exp., vaga sênior clara, presencial fora BR sem remoto, não-técnica | -10 a -40 |

**Classificação:**

| Score | Nível | Ação |
|---|---|---|
| 90-100 | Excelente oportunidade | Notificação imediata |
| 75-89 | Muito relevante | Digest + notificação |
| 60-74 | Relevante | Digest |
| 45-59 | Talvez relevante | Armazena, não notifica |
| 0-44 | Ignorar | Armazena, não notifica |

Threshold de notificação configurável (default `>= 60`).

**LLM (pós-heurístico):** recebe título, empresa, localização, modalidade, senioridade, descrição, requisitos, tecnologias, URL e retorna JSON validado:

```json
{
  "relevance_score": 0,
  "seniority_match": 0,
  "area_match": 0,
  "technology_match": 0,
  "remote_match": 0,
  "overall_match": 0,
  "recommendation": "apply|consider|ignore",
  "reason": "...",
  "missing_requirements": [],
  "matching_skills": [],
  "concerns": []
}
```

---

## Estratégia de Coleta

**Interface:**

```python
class JobSource(ABC):
    def fetch_jobs(self) -> list[RawJob]: ...
    def normalize_job(self, raw: RawJob) -> Job: ...
```

**Famílias de busca (configurável via YAML/env):**

- Simples: `"MLOps Engineer"`, `"Junior MLOps"`, `"Data Engineer"`, `"Python Developer"`, `"AI Engineer"`, etc.
- Booleanas (quando suportado): `("MLOps" OR "Machine Learning Operations") AND (Junior OR "Entry Level" OR Intern)`

Lista completa editável em `config/search_queries.yaml` — adicionar/remover queries sem alterar código.

**Fontes (modular, sem acoplamento):** LinkedIn (dentro de ToS), Indeed, Greenhouse, Lever, Workday, Ashby, Wellfound, Gupy, Programathor, sites oficiais. Prioriza APIs/feeds oficiais; nunca viola ToS/robots.txt/CAPTCHA. Quando não houver API pública, avalia alternativa legítima ou deixa fonte desabilitada.

---

## Estratégia de Notificações

**Interface:**

```python
class NotificationProvider(ABC):
    def send(self, notification: Notification) -> None: ...
```

**Implementados no MVP:** Email (SMTP) e Telegram (Bot API). **Preparados:** WhatsApp, Discord, Slack.

**Conteúdo por vaga relevante:** título, empresa, localização, modalidade, senioridade, score, principais tecnologias, *por que é relevante*, gaps, link de candidatura, data de descoberta.

**Modos:**

- **Imediato:** score >= 90 envia na hora.
- **Digest diário (08:00):** resumo — `12 novas | 5 altamente relevantes | 4 relevantes | 3 descartadas` + top 5.

Exemplo:

> **Junior Data Engineer — Empresa X** — Score: 87/100 — Remoto | Brasil
> Por que é relevante: Python, SQL, Airflow, Docker, Data Engineering
> Gaps: Experiência com AWS
> Candidatura: [link]

---

## Estrutura do Projeto

```
job-finder/
├── app/
│   ├── api/              # routers FastAPI
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── repositories/     # acesso a dados
│   ├── services/         # regras de negócio
│   ├── sources/          # adapters JobSource
│   ├── scoring/          # scoring heurístico + LLM
│   ├── notifications/    # adapters NotificationProvider
│   ├── workers/          # collector / scoring / notification workers
│   ├── core/             # config (pydantic-settings), logging, db
│   └── main.py
├── tests/
├── migrations/           # Alembic
├── scripts/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml        # uv
├── .env.example
├── README.md
└── .gitignore
```

---

## Configuração

Todas as configurações via variáveis de ambiente ou `config/*.yaml`. Nunca commitar secrets.

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db:5432/jobs` |
| `REDIS_URL` | `redis://redis:6379/0` (se usar Celery) |
| `TELEGRAM_BOT_TOKEN` | Token do bot |
| `TELEGRAM_CHAT_ID` | Chat destino |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` | Email |
| `OPENAI_API_KEY` | LLM OpenAI (opcional) |
| `OLLAMA_BASE_URL` | Ollama host: `http://localhost:11434` (local), `http://ollama:11434` (Docker), `https://ollama.com` (Cloud gratuito) |
| `OLLAMA_MODEL` | Local: `llama3.1:8b`, `qwen2.5:7b` · Cloud free: `gpt-oss:20b-cloud`, `qwen3-coder:480b-cloud`, `deepseek-v3.1:671b-cloud` |
| `OLLAMA_API_KEY` | API key Ollama Cloud — crie em https://ollama.com/settings/keys (necessário só para Cloud) |
| `LLM_PROVIDER` | `auto` (tenta Ollama → OpenAI → disabled), `ollama`, `openai`, `disabled` |
| `SCORE_THRESHOLD` | Default 60 |
| `DIGEST_TIME` | Default 08:00 |
| `LOG_LEVEL` | `INFO` / `DEBUG` |

Veja `.env.example` para lista completa.

### Ollama — Local grátis vs Cloud gratuito

**Possibilidade confirmada: sim, há opção cloud gratuita.**

| Modo | Custo | Como usar | Quando usar |
|---|---|---|---|
| **Local** | 100% grátis, offline | `OLLAMA_BASE_URL=http://localhost:11434` + `docker compose --profile ollama up -d` + `docker exec ollama ollama pull llama3.1:8b` | Sem dependência de internet, privacidade total, sem limite de uso. Requer RAM/VRAM local. |
| **Cloud Free Tier** | Grátis (light usage) | `OLLAMA_BASE_URL=https://ollama.com` + `OLLAMA_API_KEY=sua_key` + `OLLAMA_MODEL=gpt-oss:20b-cloud` — crie conta em https://ollama.com e key em https://ollama.com/settings/keys | Sem GPU local. Free tier inclui quota base (reset a cada 5h/semana), modelos leves–médios (`*-cloud`), concorrência limitada. Suficiente para Fase 6 (classificação pós-filtro, poucas vagas/dia). Ilimitado local não consome quota. |

Ambos usam mesma API (`/api/chat` e OpenAI-compat `/v1/chat/completions`) — o código em `app/scoring/llm.py:88-157` já suporta local e cloud via `OLLAMA_BASE_URL` + `OLLAMA_API_KEY` (header `Authorization: Bearer`). `LLM_PROVIDER=auto` prefere Ollama (local ou cloud) se `health_check()` ok, senão OpenAI.

**Recomendação para este projeto (baixo custo):** comece com Ollama Cloud free (`gpt-oss:20b-cloud`) para validar Fase 6 sem instalar nada local; se atingir quota, mude para local `llama3.1:8b` ou mantenha cloud com modelos nível 1-2 (consomem menos). Só o LLM classifica vagas candidatas (`score >= threshold`), então custo/uso é mínimo.

---

## Como Executar Localmente

**Pré-requisitos:** Docker, Docker Compose, `uv` (para dev local sem Docker).

### Com Docker (recomendado)

```bash
cp .env.example .env
# edite .env com suas credenciais
docker compose up --build
# API em http://localhost:8000 | docs em /docs
```

Serviços: `api`, `db` (PostgreSQL), `worker`, `scheduler` (+ `redis` se habilitado).

#### Ollama Local (opcional, 100% grátis)

```bash
docker compose --profile ollama up -d
docker exec projeto_vagas-ollama-1 ollama pull llama3.1:8b
# .env: OLLAMA_BASE_URL=http://ollama:11434  OLLAMA_MODEL=llama3.1:8b  LLM_PROVIDER=ollama
```

#### Ollama Cloud Gratuito (sem GPU local)

```bash
# 1. Crie conta em https://ollama.com e gere API key em https://ollama.com/settings/keys
# 2. Configure .env:
# OLLAMA_BASE_URL=https://ollama.com
# OLLAMA_API_KEY=ollama_xxxxx
# OLLAMA_MODEL=gpt-oss:20b-cloud  # ou qwen3-coder:480b-cloud
# LLM_PROVIDER=ollama  # ou auto

curl https://ollama.com/api/tags -H "Authorization: Bearer $OLLAMA_API_KEY" # testa cloud
# Sem Docker Ollama necessário — a API classifica direto na nuvem free tier
```

### Sem Docker (desenvolvimento)

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
# em outro terminal
uv run python -m app.workers.scheduler
```

---

## API

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/jobs` | Lista vagas (filtros: score, área, modalidade) |
| GET | `/jobs/{id}` | Detalhe da vaga |
| GET | `/jobs/recommended` | Vagas recomendadas (score >= threshold) |
| GET | `/jobs/search/text` | Busca textual ILIKE |
| GET | `/sources` | Lista fontes |
| POST | `/sources/ingest` | Ingere todas fontes (com scoring+notificação) |
| GET | `/sources/preview/{name}` | Preview normalizado + scoring sem persistir |
| GET | `/sources/queries` | Lista queries YAML (21) |
| GET | `/notifications` | Histórico notificações |
| GET | `/notifications/digest` | Digest diário |
| GET | `/notifications/providers` | Status Telegram/Email |
| POST | `/notifications/test` | Envio teste |
| GET | `/scoring/llm/status` | Status LLM provider |
| POST | `/scoring/llm/classify` | Classifica vaga com LLM |
| POST | `/scoring/recompute/{id}` | Recomputa score heurístico+LLM |
| GET | `/worker/status` | Status scheduler |
| POST | `/worker/run` | Pipeline manual |
| GET | `/metrics` | Métricas Prometheus |
| GET | `/observability` | Estatísticas JSON |
| GET | `/health/detailed` | Health detalhado |

Docs interativas: `http://localhost:8000/docs` (Swagger) e `/redoc`.

---

## Observabilidade

- **Logging estruturado** `app/core/logging.py:1` — `text` default ou `LOG_FORMAT=json` (JSON com `timestamp/level/logger/message/metrics`, pronto para Loki/Grafana), `uvicorn.access` silenciado, secrets nunca logados.
- **Métricas por execução** `app/workers/runner.py:44` + `app/core/metrics.py:1` — `collected`, `new`, `duplicates`, `discarded`, `errors`, `errors_by_source`, `notifications_sent`, `elapsed_s`, histórico últimas 100 execuções (`record_run()`), `GET /observability` (JSON) e `GET /metrics` (Prometheus text `job_finder_jobs_total`, `by_classification`, pronto para Grafana).
- **Tratamento de exceções** por fonte (falha de uma não derruba pipeline, `ingest_all()` isola), por LLM, por provider notificação.
- **Health detalhado** `GET /health/detailed` — db, llm, scheduler, notifications, stats.
- **Pronto para Prometheus/Grafana** — endpoint `/metrics` (`text/plain; version=0.0.4`).

---

## Testes

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

Cobertura para: normalização, deduplicação, scoring, filtros, classificação, repositories, API, notificações, integração com banco. Mocks para fontes externas — testes nunca dependem de LinkedIn/serviços reais.

---

## Plano de Implementação por Etapas

| Fase | Entregas | Status |
|---|---|---|
| **1** | FastAPI + PostgreSQL + SQLAlchemy + Alembic + modelo Job + config `pydantic-settings` | ✅ Concluída |
| **2** | Sistema de fontes (`JobSource`), 1ª fonte legítima (Arbeitnow API), normalização, deduplicação (fingerprint) | ✅ Concluída |
| **3** | Sistema de queries configurável (`config/search_queries.yaml` 21 queries), filtros, scoring heurístico 0-100 (senioridade/área/modalidade/techs + penalidades + cap) | ✅ Concluída |
| **4** | Notificações Telegram + Email (adapter `NotificationProvider.send()`, `TelegramProvider`, `EmailProvider`, `format_job_message()`, thresholds 60 digest / 90 imediato, digest diário) | ✅ Concluída |
| **5** | Scheduler/worker (APScheduler monólito modular, `app/workers/runner.py` pipeline, `app/workers/scheduler.py` coleta 60min + digest 08:00, `docker compose --profile worker up`, `POST /worker/run` manual) — justificado vs Celery (MVP sem broker) | ✅ Concluída |
| **6** | LLM para classificação avançada (pós-filtro, JSON validado `LLMClassification`, `OllamaProvider` local+Cloud `https://ollama.com` free `gpt-oss:20b-cloud`, `OpenAIProvider`, custo-controlado só se heuristic>=60, `score_and_persist()` média 70/30, `GET /scoring/llm/status`, `POST /scoring/llm/classify`, `POST /scoring/recompute/{id}`) | ✅ Concluída |
| **7** | Observabilidade (`app/core/metrics.py`, `/metrics` Prometheus, `/observability`, `/health/detailed`, `LOG_FORMAT=json`), testes 49, Docker `docker-compose.yml` api/db/worker/scheduler/ollama, documentação completa, deploy | ✅ Concluída |

Cada fase mantém o sistema funcional (MVP incremental).

---

## Deploy

Opções baratas para MVP 24/7:

| Opção | Custo aprox. | Prós | Contras |
|---|---|---|---|
| **Railway / Render / Fly.io** | $5-10/mês | Deploy simples, PostgreSQL gerenciado, workers | Cold start (Render free), limites |
| **VPS (Hetzner, DigitalOcean)** | $4-6/mês | Controle total, persistência garantida | Gerenciar Docker/postgres manual |
| **Oracle Cloud Free Tier** | Grátis | 2 VMs + DB grátis | Setup mais complexo |

Todos suportam: `docker compose`, secrets via env, volume persistente para PostgreSQL, healthcheck da API.

---

## Segurança e Compliance

- Secrets apenas via env; nunca no Git.
- Validação de inputs (Pydantic), rate limiting, autenticação em endpoints admin.
- Sanitização de dados de fontes externas.
- Respeito a ToS/robots.txt — sem bypass de CAPTCHA/auth.

---

## Licença

Defina a licença desejada (ex: MIT). Adicione `LICENSE` ao repositório antes de publicar.

---

*Especificação original em [`Agente de busca automatizada de vagas.md`](./Agente%20de%20busca%20automatizada%20de%20vagas.md).*
