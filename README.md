# Job Finder

Agente automatizado de busca, filtragem, ranqueamento e notificação de vagas de emprego. Focado em oportunidades de **Estágio, Júnior e Entry-level** nas áreas de MLOps, Engenharia de Software, Engenharia de Dados e Ciência de Dados.

O pipeline roda periodicamente, calcula a aderência real de cada vaga ao perfil e notifica apenas as oportunidades relevantes.

```
[Scheduler] → [Coleta] → [Normalização] → [Deduplicação] → [Filtro Heurístico]
           → [Score 0-100] → [LLM opcional] → [PostgreSQL] → [Email / Telegram]
```

---

## Funcionalidades

- Coleta de vagas em múltiplas fontes com adapters plugáveis.
- Normalização e deduplicação por fingerprint estável.
- Scoring heurístico de 0 a 100 (senioridade, área, modalidade, tecnologias e penalidades).
- Classificação opcional por LLM (Ollama local/cloud ou OpenAI), com custo controlado.
- Notificações por Telegram e Email, com envio imediato e digest diário.
- API REST com documentação Swagger e interface web simples em `/ui`.
- Observabilidade com métricas Prometheus, logs estruturados e health check detalhado.
- Scheduler embutido (APScheduler) e execução manual via API.

---

## Stack

| Camada | Tecnologia |
|---|---|
| API | FastAPI, Pydantic, SQLAlchemy, Alembic |
| Banco | PostgreSQL |
| Scheduler | APScheduler |
| LLM | Ollama (local ou cloud) e OpenAI (opcional) |
| Gerenciador Python | `uv` |
| Containers | Docker e Docker Compose |
| Testes / Lint | pytest, ruff |

---

## Perfil Alvo
Você pode escolher, desde a senioridade até áreas de interesse.

- **Senioridade:**
- **Áreas prioritárias:**
- **Áreas secundárias:**
- **Localização:**
- **Stack de interesse:**

---

## Arquitetura

Monólito modular, com adapters para fontes e notificações. A separação em serviços só é necessária quando houver demanda real de escala.

| Componente | Responsabilidade |
|---|---|
| **Collector** | Busca vagas nas fontes configuradas |
| **Scoring** | Aplica filtros, score heurístico e LLM opcional |
| **Notification** | Envia notificações individuais e digest diário |
| **API** | Consulta de vagas, fontes, notificações e status |
| **Scheduler** | Orquestra a execução periódica do pipeline |
| **PostgreSQL** | Persistência de vagas, scores e histórico |

### Fluxo

1. O scheduler dispara o pipeline (intervalo configurável, padrão 60 min).
2. Cada fonte coleta e normaliza as vagas.
3. O fingerprint evita duplicatas e re-notificações.
4. O filtro heurístico descarta vagas sem aderência.
5. O score de 0 a 100 é calculado e persistido.
6. Vagas acima do threshold passam pela classificação LLM (opcional).
7. Notificações são enviadas na hora ou no digest diário.

---

## Scoring

Score final de 0 a 100, com limites por categoria para evitar inflação por palavras-chave.
Os níveis de scoring você também decide.

| Dimensão | Regra | Pontos |
|---|---|---|
| **Senioridade** | Estágio / Júnior | +25 |
| | Entry-level | +20 |
| | Trainee | +15 |
| | Pleno | -20 |
| | Sênior | -50 |
| | Staff / Principal / Lead | -80 |
| **Área** | MLOps / MLE / Data Eng. | +25 |
| | Software Eng. / Data Science / AI Eng. | +20 |
| | Backend / DevOps / Analytics Eng. | +15 |
| | Data Analyst | +5 |
| **Modalidade** | Remoto no Brasil | +25 |
| | Remoto | +20 |
| | Híbrido | +5 |
| | Presencial | -10 |
| **Tecnologias** | Stack de interesse | +3 a +5 cada (com limite) |
| **Penalidades** | Exigência de 5+ anos, vaga sênior, presencial fora do Brasil, vaga não técnica | -10 a -40 |

| Score | Classificação | Ação |
|---|---|---|
| 90-100 | Excelente | Notificação imediata |
| 75-89 | Muito relevante | Digest + notificação |
| 60-74 | Relevante | Digest |
| 45-59 | Talvez relevante | Armazena |
| 0-44 | Ignorar | Armazena |

O threshold de notificação é configurável (padrão `60`).

---

## Fontes de Dados

O sistema usa o pattern adapter (`fetch_jobs()` / `normalize_job()`), permitindo adicionar ou remover fontes sem alterar o pipeline.

**Fontes implementadas:** Arbeitnow, LinkedIn, Vagas.com, Eureca, Cia de Talentos, Academia, Gupy, Programathor e Greenhouse.

As buscas ficam em [`config/search_queries.yaml`](config/search_queries.yaml) e podem ser editadas sem alterar código. O sistema respeita os termos de uso das fontes e não realiza bypass de CAPTCHA ou autenticação.

---

## Notificações

Implementadas via `NotificationProvider`:

- **Telegram** (Bot API)
- **Email** (SMTP)
- **Preparados para expansão:** WhatsApp, Discord, Slack

Cada vaga notificada inclui título, empresa, localização, modalidade, senioridade, score, tecnologias, justificativa de relevância, gaps e link de candidatura.

---

## Como Executar

### Pré-requisitos

- Docker e Docker Compose
- `uv` (apenas para desenvolvimento sem Docker)

### Com Docker (recomendado)

```bash
cp .env.example .env
# edite o .env com suas credenciais

docker compose up --build -d
```

- API: http://localhost:8000
- Documentação: http://localhost:8000/docs
- Interface web: http://localhost:8000/ui

Para habilitar o worker/scheduler:

```bash
docker compose --profile worker up --build -d
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

O LLM só classifica vagas que já passaram pelo filtro heurístico, mantendo o custo baixo.

**Ollama local (grátis e offline):**

```bash
docker compose --profile ollama up -d
docker exec projeto_vagas-ollama-1 ollama pull llama3.1:8b
```

```env
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.1:8b
LLM_PROVIDER=ollama
```

**Ollama Cloud (free tier, sem GPU local):**

```env
OLLAMA_BASE_URL=https://ollama.com
OLLAMA_API_KEY=sua_key
OLLAMA_MODEL=gpt-oss:20b-cloud
LLM_PROVIDER=ollama
```

Crie a API key em https://ollama.com/settings/keys.

Para desabilitar o LLM, use `LLM_PROVIDER=disabled`.

---

## Testes

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

Cobertura de normalização, deduplicação, scoring, filtros, classificação, repositories, API, notificações e integração com banco. Fontes externas são mockadas — os testes não dependem de serviços reais.

---

## Observabilidade

- **Logs estruturados** (`LOG_FORMAT=json`) prontos para Loki/Grafana.
- **Métricas por execução:** coletadas, novas, duplicadas, descartadas, erros por fonte, notificações enviadas e tempo.
- **Prometheus:** `GET /metrics`.
- **Health detalhado:** `GET /health/detailed`.
- Falhas em uma fonte ou provider não derrubam o pipeline.

---

## Estrutura do Projeto

```
projeto_vagas/
├── app/
│   ├── api/              # routers FastAPI
│   ├── core/             # config, logging, database, metrics
│   ├── models/           # modelos SQLAlchemy
│   ├── schemas/          # schemas Pydantic
│   ├── services/         # normalização, deduplicação, ingestão, scoring
│   ├── scoring/          # heurístico, filtros e LLM
│   ├── sources/          # adapters de fontes de vagas
│   ├── notifications/    # adapters de notificação
│   ├── workers/          # runner e scheduler
│   ├── static/           # interface web
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

## Segurança

- Secrets apenas via variáveis de ambiente, nunca no Git.
- Validação de entrada com Pydantic.
- Sanitização de dados vindos de fontes externas.
- Respeito aos termos de uso e `robots.txt` das fontes.

---

## Licença
MIT
