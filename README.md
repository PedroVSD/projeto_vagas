# Job Finder

Serviço de coleta, normalização, deduplicação, scoring e notificação de vagas de emprego. A aplicação expõe uma API REST (FastAPI), uma interface web em `/ui` e um pipeline executável por scheduler ou manualmente.

```
[Scheduler] → [Coleta] → [Normalização] → [Deduplicação] → [Filtro Heurístico]
           → [Score 0-100] → [LLM opcional] → [PostgreSQL] → [Email / Telegram]
```

---

## Stack

| Camada | Tecnologia |
|---|---|
| API | FastAPI, Pydantic, SQLAlchemy, Alembic |
| Banco | PostgreSQL 16 |
| Scheduler | APScheduler |
| LLM | Ollama (local/cloud) e OpenAI (opcional) |
| Gerenciador Python | `uv` |
| Containers | Docker e Docker Compose |
| Testes / Lint | pytest, ruff |

---

## Arquitetura

Monólito modular com adapters para fontes de vagas e providers de notificação.

| Componente | Responsabilidade |
|---|---|
| **Collector** | Coleta vagas nas fontes configuradas |
| **Normalization** | Padroniza campos (título, local, modalidade, senioridade, tecnologias) |
| **Deduplication** | Gera fingerprint estável e evita vagas duplicadas |
| **Scoring** | Filtro heurístico, score 0–100 e classificação LLM opcional |
| **Notification** | Envio imediato e digest diário (Telegram/SMTP) |
| **API** | Consulta de vagas, fontes, notificações e status |
| **Scheduler** | Dispara o pipeline em intervalo configurável |
| **PostgreSQL** | Persiste vagas, scores, notificações e histórico |

### Fluxo do pipeline

1. O scheduler (ou `POST /worker/run`) inicia a execução.
2. Cada fonte implementa `fetch_jobs()` e `normalize_job()`.
3. O fingerprint elimina duplicatas e re-notificações.
4. O filtro heurístico descarta vagas sem aderência.
5. O score é calculado e persistido em `job_scores`.
6. Vagas acima do threshold podem passar pelo LLM.
7. Notificações são enviadas imediatamente ou no digest diário.

---

## Estrutura do Projeto

```
projeto_vagas/
├── app/
│   ├── api/              # routers FastAPI
│   ├── core/             # config, logging, database, métricas
│   ├── models/           # modelos SQLAlchemy
│   ├── schemas/          # schemas Pydantic
│   ├── services/         # normalização, deduplicação, ingestão, scoring
│   ├── scoring/          # heurístico, filtros e LLM
│   ├── sources/          # adapters de fontes de vagas
│   ├── notifications/    # adapters de notificação
│   ├── workers/          # runner e scheduler
│   ├── static/           # interface web
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   └── main.py
├── config/
│   └── search_queries.yaml
├── migrations/           # Alembic
├── scripts/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Configuração

Copie o arquivo de exemplo e ajuste as variáveis:

```bash
cp .env.example .env
```

### Variáveis principais

| Variável | Padrão | Descrição |
|---|---|---|
| `APP_ENV` | `development` | Ambiente da aplicação |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/job_finder` | Conexão PostgreSQL |
| `SCORE_THRESHOLD` | `60` | Score mínimo para digest |
| `IMMEDIATE_THRESHOLD` | `90` | Score mínimo para envio imediato |
| `LLM_PROVIDER` | `auto` | `ollama`, `openai`, `auto` ou `disabled` |
| `LLM_ENABLED` | `true` | Habilita classificação por LLM |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | — | Credenciais do Telegram |
| `SMTP_HOST` / `SMTP_TO` | — | Credenciais SMTP |
| `SCHEDULER_ENABLED` | `true` | Liga o scheduler |
| `SCHEDULER_INTERVAL_MINUTES` | `60` | Intervalo de coleta |
| `DIGEST_ENABLED` / `DIGEST_TIME` | `true` / `08:00` | Digest diário |
| `LOG_FORMAT` | `text` | `text` ou `json` |

### Queries de busca

As buscas são externalizadas em `config/search_queries.yaml` (seções `simple`, `boolean`, `search_profiles`, `settings` e `throttling`). O arquivo pode ser editado sem alterar código e é carregado pela API e pelas fontes.

---

## Como Executar

### Docker (recomendado)

```bash
cp .env.example .env
docker compose up --build -d
```

Serviços iniciados:

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Frontend: http://localhost:8000/ui
- PostgreSQL: `localhost:5432`

As migrações Alembic são executadas automaticamente no start do container da API.

### Worker / scheduler

```bash
docker compose --profile worker up --build -d
# ou
docker compose --profile scheduler up --build -d
```

### Sem Docker

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# em outro terminal
uv run python -m app.workers.scheduler
```

### LLM (opcional)

O LLM só classifica vagas que já passaram pelo filtro heurístico, mantendo o custo controlado.

**Ollama local:**

```bash
docker compose --profile ollama up -d
docker exec projeto_vagas-ollama-1 ollama pull llama3.1:8b
```

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
```

**Ollama Cloud:**

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=sua_key
OLLAMA_MODEL=gpt-oss:20b-cloud
```

Para desabilitar: `LLM_PROVIDER=disabled`.

---

## API

Documentação interativa em `/docs` e `/redoc`.

Exemplos:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/jobs/recommended?threshold=60&limit=5"
curl -X POST http://localhost:8000/sources/ingest/linkedin
curl -X POST http://localhost:8000/worker/run
```

---

## Frontend

A interface em `/ui` é um SPA estático (HTML/CSS/JS, sem build) servido pelo FastAPI. Ela consome a mesma API por caminhos relativos, sem necessidade de CORS adicional.

Views disponíveis:

- **Dashboard:** KPIs, classificação por score, execuções recentes e saúde dos componentes.
- **Vagas:** recomendadas, listagem paginada com filtros e busca textual.
- **Fontes:** ingestão individual/em lote, preview com score e queries configuradas.
- **Notificações:** providers, digest, histórico e envio de teste.
- **Scoring / LLM:** status do provider, classificação manual e recomputação.
- **Worker:** status do scheduler e execução manual do pipeline/digest.
- **Sistema:** health, observabilidade, métricas e resposta do root.

### Como testar a API com o frontend

1. Suba o banco e a API:

   ```bash
   cp .env.example .env
   docker compose up --build -d
   ```

2. Abra http://localhost:8000/ui e confirme que o badge de health fica **ok** no topo e na sidebar.

3. Popule o banco pela própria interface:
   - Acesse **Fontes** → **Ingerir** em uma fonte (ex.: `linkedin`), ou marque várias e use **Ingerir selecionadas**.
   - Alternativamente, em **Worker**, clique em **Rodar pipeline**.

4. Volte para **Vagas** → **Recomendadas** e ajuste o threshold. Clique em **Detalhes** para ver o JSON da vaga e **Recomputar score**.

5. Valide os demais fluxos:
   - **Fontes** → **Preview** de uma fonte (mostra score sem persistir).
   - **Notificações** → **Enviar teste** (sem credenciais retorna payload de exemplo).
   - **Scoring / LLM** → **Classificar** (requer LLM habilitado).
   - **Sistema** → confira `/health/db`, `/metrics` e `/observability`.

6. Para validar a API fora da interface, use o Swagger em http://localhost:8000/docs ou os exemplos `curl` acima.

> Se a interface abrir, mas as listas retornarem erro de banco, verifique `docker compose ps` e os logs com `docker compose logs -f api`. O dashboard usa requisições independentes (`Promise.allSettled`), portanto permanece funcional mesmo com o banco indisponível.

---

## Notificações

Implementadas via interface `NotificationProvider`:

- Telegram (Bot API)
- Email (SMTP)
- Pontos de extensão para WhatsApp, Discord e Slack

Cada notificação inclui título, empresa, local, modalidade, senioridade, score, tecnologias, justificativa, gaps e link de candidatura.

---

## Testes e Qualidade

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check app tests
```

Fontes externas são mockadas; os testes não dependem de serviços reais.

---

## Observabilidade

- Logs estruturados com `LOG_FORMAT=json` (pronto para Loki/Grafana).
- Métricas por execução: coletadas, novas, duplicadas, descartadas, erros por fonte, notificações e tempo.
- Prometheus: `GET /metrics`.
- Health detalhado: `GET /health/detailed`.
- Falhas em uma fonte/provider não derrubam o pipeline.

---

## Licença

Consulte [LICENSE](LICENSE).
