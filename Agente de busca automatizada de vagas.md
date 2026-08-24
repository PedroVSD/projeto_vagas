Quero que você projete e implemente um serviço automatizado de busca, filtragem, ranqueamento e notificação de vagas de emprego relevantes para o meu perfil.

O objetivo é criar um sistema que rode continuamente, busque novas vagas em intervalos regulares, determine quais realmente são relevantes para mim e envie apenas as melhores oportunidades por um ou mais canais de notificação.

## 1. Meu perfil

Estou buscando principalmente oportunidades de:

- Estágio
- Júnior
- Entry-level
- Trainee, quando houver aderência técnica

Áreas prioritárias:

1. MLOps
2. Engenharia de Software
3. Engenharia de Dados
4. Ciência de Dados

Áreas secundárias que podem ser consideradas quando houver boa aderência:

- Machine Learning Engineer
- ML Engineer
- Data Engineer
- Backend Engineer
- Python Developer
- Software Engineer
- AI Engineer
- Data Analyst, desde que tenha forte componente técnico
- Platform Engineer
- DevOps Engineer, especialmente quando houver relação com ML/data
- Cloud Engineer, especialmente quando houver relação com dados/ML
- Analytics Engineer
- NLP Engineer
- AI/ML Intern
- Research/Applied ML Intern
- Data/ML Platform Engineer

Tenho interesse especial em vagas que utilizem tecnologias como:

- Python
- Go/Golang
- SQL
- Docker
- Kubernetes
- FastAPI
- Git/GitHub
- Linux
- AWS
- GCP
- Azure
- Apache Airflow
- Apache Spark/PySpark
- Databricks
- MLflow
- CI/CD
- APIs
- REST
- PostgreSQL
- Redis
- Kafka
- Machine Learning
- NLP
- LLMs
- MLOps
- Data Engineering
- Cloud

Não quero que o sistema exija que uma vaga contenha todas essas tecnologias. Elas devem ser utilizadas para medir aderência.

## 2. Localização

Prioridade:

1. Remoto
2. Remoto no Brasil
3. Híbrido no Brasil
4. Presencial no Brasil, somente se a oportunidade for excepcionalmente relevante

Dar preferência para empresas que aceitem candidatos residentes no Brasil.

Não descartar automaticamente vagas internacionais remotas. Se uma empresa contratar remotamente no Brasil, a vaga deve receber pontuação alta.

## 3. Objetivo do sistema

O sistema deve executar periodicamente um pipeline semelhante a:

Coleta → Normalização → Deduplicação → Classificação → Scoring → Filtragem → Notificação → Persistência

O sistema deve procurar vagas novas desde a última execução.

Não quero receber repetidamente a mesma vaga.

Cada vaga deve possuir um identificador estável ou um fingerprint calculado a partir de informações como:

- empresa
- título
- localização
- URL
- descrição

Se a mesma vaga aparecer em múltiplas fontes, consolidar em um único registro.

## 4. Fontes de vagas

O sistema deve ser modular para permitir adicionar fontes posteriormente.

Priorizar fontes que ofereçam APIs, feeds ou mecanismos oficialmente permitidos.

Possíveis fontes:

- LinkedIn, respeitando suas regras e limitações
- Indeed
- Greenhouse
- Lever
- Workday
- Ashby
- Wellfound
- Gupy
- Programathor
- Sites oficiais das empresas
- Outros job boards relevantes

IMPORTANTE:

Não implemente scraping de forma que viole Terms of Service, robots.txt, autenticação, CAPTCHA ou mecanismos de proteção das plataformas.

Quando uma fonte não possuir uma API pública adequada, avaliar alternativas legítimas.

A arquitetura deve permitir adicionar/remover fontes sem modificar o restante do sistema.

Criar uma interface abstrata semelhante a:

JobSource
    fetch_jobs()
    normalize_job()

Cada fonte deve possuir sua própria implementação.

## 5. Busca

Não utilizar apenas uma query.

Criar várias famílias de buscas.

Exemplos:

"MLOps Engineer"
"Junior MLOps"
"Machine Learning Engineer"
"Junior Machine Learning Engineer"
"ML Engineer"
"Data Engineer"
"Junior Data Engineer"
"Software Engineer Python"
"Backend Engineer Python"
"Junior Software Engineer"
"Python Developer"
"Data Scientist"
"Junior Data Scientist"
"AI Engineer"
"ML Engineer Intern"
"Data Engineer Intern"
"Software Engineer Intern"

Também criar buscas booleanas quando a fonte suportar.

Exemplos:

("MLOps" OR "Machine Learning Operations") AND (Junior OR "Entry Level" OR Intern OR Internship)

("Machine Learning Engineer" OR "ML Engineer") AND (Junior OR Intern OR "Entry Level")

("Data Engineer" OR "Data Engineering") AND (Junior OR Intern OR "Entry Level")

("Software Engineer" OR "Backend Engineer" OR "Python Developer") AND (Python OR FastAPI OR Go OR Golang) AND (Junior OR Intern OR "Entry Level")

Não limitar o sistema a essas queries. Criar uma configuração facilmente editável.

## 6. Sistema de scoring

Cada vaga deve receber uma pontuação de relevância de 0 a 100.

O scoring deve considerar pelo menos:

### Senioridade

Estágio/Internship: +25
Junior: +25
Entry-level: +20
Trainee: +15
Pleno: -20
Senior: -50
Staff/Principal/Lead: -80

Se a vaga não informar claramente a senioridade, inferir a partir da descrição, mas reduzir a confiança.

### Área

MLOps: +25
Machine Learning Engineering: +25
Data Engineering: +25
Software Engineering: +20
Data Science: +20
AI Engineering: +20
Backend: +15
DevOps/Platform: +15
Analytics Engineering: +15
Data Analyst: +5

### Modalidade

Remoto: +20
Remoto no Brasil: +25
Híbrido: +5
Presencial: -10

### Tecnologias

Adicionar pontos conforme a aderência ao meu perfil.

Exemplo:

Python: +5
Go/Golang: +5
Docker: +5
Kubernetes: +5
AWS: +4
GCP: +4
Azure: +3
Airflow: +5
Spark/PySpark: +5
Databricks: +5
MLflow: +5
FastAPI: +4
SQL: +4
PostgreSQL: +3
Kafka: +4
CI/CD: +4
Machine Learning: +5
NLP: +5
LLM/Generative AI: +5

Criar limites para evitar que uma vaga ganhe pontuação excessiva simplesmente por mencionar muitas tecnologias.

### Penalidades

Aplicar penalidades quando:

- exigir experiência incompatível com estágio/júnior;
- exigir muitos anos de experiência;
- for claramente uma vaga sênior;
- exigir localização fora do Brasil sem possibilidade remota;
- não possuir nenhuma relação significativa com software, dados ou ML;
- for predominantemente não técnica.

## 7. Classificação por nível de interesse

Depois do score:

90-100: Excelente oportunidade
75-89: Muito relevante
60-74: Relevante
45-59: Talvez relevante
0-44: Ignorar

Por padrão, enviar notificações somente para vagas >= 60.

Permitir configurar esse threshold.

## 8. LLM para classificação

Avaliar a utilização de um LLM depois do scoring heurístico.

Não utilizar o LLM para todas as vagas indiscriminadamente, pois isso pode gerar custo desnecessário.

Primeiro aplicar filtros determinísticos.

Depois utilizar o LLM somente nas vagas candidatas.

O LLM deve receber:

- título
- empresa
- localização
- modalidade
- senioridade
- descrição
- requisitos
- tecnologias
- URL

E retornar JSON estruturado:

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

Não permitir que a saída livre do LLM controle diretamente o sistema. Validar o JSON com um schema.

## 9. Notificações

Criar uma arquitetura de notificações baseada em adapters.

Interface:

NotificationProvider
    send(notification)

Implementar inicialmente:

- Email
- Telegram

Deixar a arquitetura preparada para:

- WhatsApp
- Discord
- Slack

Não acoplar a lógica de negócio a nenhum desses canais.

Cada vaga relevante deve gerar uma notificação contendo:

Título
Empresa
Localização
Modalidade
Senioridade
Score
Principais tecnologias
Por que a vaga é relevante
Possíveis gaps
Link para candidatura
Data em que foi encontrada

Exemplo conceitual:

"Junior Data Engineer — Empresa X"

Score: 87/100
Modalidade: Remoto
Localização: Brasil

Por que é relevante:
- Python
- SQL
- Airflow
- Docker
- Data Engineering

Gaps:
- Experiência com AWS

Candidatura:
[link]

## 10. Digest

Além de notificações individuais, implementar um modo digest.

Exemplo:

Todos os dias às 08:00:

"12 novas vagas encontradas
5 altamente relevantes
4 relevantes
3 descartadas"

Mostrar as 5 melhores.

Também permitir uma notificação imediata para vagas acima de determinado score, por exemplo >= 90.

## 11. Banco de dados

Utilizar PostgreSQL.

Criar entidades aproximadamente como:

Job
Company
JobSource
JobScore
Notification
SearchQuery
UserPreference

O modelo deve permitir:

- histórico de vagas;
- histórico de scores;
- histórico de notificações;
- saber quando uma vaga foi encontrada;
- saber quando foi notificada;
- saber se já foi enviada;
- atualizar informações de uma vaga;
- acompanhar mudanças na descrição.

Criar índices adequados.

Evitar duplicação.

## 12. API

Criar uma API utilizando FastAPI.

Endpoints sugeridos:

GET /jobs
GET /jobs/{id}
GET /jobs/recommended
GET /jobs/search
POST /jobs/search
GET /sources
POST /sources
GET /preferences
PUT /preferences
GET /notifications
POST /notifications/test

Também criar endpoints administrativos quando necessário.

Utilizar:

- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL

Manter separação clara entre:

routers
schemas
models
services
repositories
sources
scoring
notifications
workers
configuration

## 13. Jobs periódicos

O sistema precisa executar automaticamente.

Avaliar opções como:

- Celery + Redis
- APScheduler
- cron
- worker próprio

Escolher a solução mais simples que seja adequada ao projeto.

Como o objetivo também é aprendizado, justificar a escolha.

Idealmente o sistema deve ter:

Collector Worker
Scoring Worker
Notification Worker

Mas evitar microservices prematuramente.

Começar como um monólito modular e somente separar componentes quando houver necessidade real.

## 14. Docker

Criar Docker Compose contendo inicialmente:

- API
- PostgreSQL
- Redis, caso seja necessário
- Worker
- Scheduler

O sistema deve ser executável localmente com poucos comandos.

Fornecer:

Dockerfile
docker-compose.yml
.env.example

Nunca colocar secrets no código.

## 15. Configuração

Todas as configurações importantes devem estar em variáveis de ambiente ou arquivos de configuração.

Exemplos:

DATABASE_URL
REDIS_URL
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
OPENAI_API_KEY

Nunca armazenar secrets no Git.

## 16. Observabilidade

Adicionar:

- logging estruturado;
- tratamento de exceções;
- métricas básicas;
- quantidade de vagas coletadas;
- quantidade de vagas novas;
- quantidade duplicada;
- quantidade descartada;
- quantidade enviada;
- tempo de execução;
- erros por fonte.

Preparar a arquitetura para futuramente utilizar Prometheus/Grafana.

## 17. Testes

Criar testes para:

- normalização de vagas;
- deduplicação;
- scoring;
- filtros;
- classificação;
- repositories;
- API;
- notificações;
- integração com banco.

Criar mocks para fontes externas.

Não fazer testes dependerem de LinkedIn ou outros serviços externos reais.

## 18. Segurança

Considerar:

- secrets via environment variables;
- validação de inputs;
- rate limiting quando necessário;
- autenticação da API administrativa;
- proteção dos endpoints internos;
- logs sem exposição de tokens/secrets;
- sanitização dos dados provenientes das fontes.

## 19. Interface

Não é necessário criar um frontend complexo inicialmente.

Se fizer sentido, criar uma interface simples ou deixar a API preparada para um frontend futuro.

O MVP deve priorizar:

1. coleta;
2. classificação;
3. deduplicação;
4. ranking;
5. notificação.

## 20. GitHub

Criar um projeto organizado para publicação no GitHub.

Estrutura aproximada:

job-finder/
├── app/
│   ├── api/
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── sources/
│   ├── scoring/
│   ├── notifications/
│   ├── workers/
│   ├── core/
│   └── main.py
├── tests/
├── migrations/
├── scripts/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── .env.example
├── README.md
└── .gitignore

Estou utilizando uv para gerenciamento de dependências Python. Preferir uv em vez de pip.

## 21. Desenvolvimento incremental

Não tente construir tudo de uma vez.

Primeiro apresente a arquitetura proposta e explique as principais decisões.

Depois implemente em etapas:

Fase 1:
- projeto FastAPI;
- PostgreSQL;
- SQLAlchemy;
- Alembic;
- modelo Job;
- configuração com pydantic-settings.

Fase 2:
- sistema de fontes;
- primeira fonte legítima de vagas;
- normalização;
- deduplicação.

Fase 3:
- sistema de queries;
- filtros;
- scoring heurístico.

Fase 4:
- notificações por Telegram e e-mail.

Fase 5:
- scheduler/worker;
- execução automática.

Fase 6:
- LLM para classificação avançada.

Fase 7:
- observabilidade;
- testes;
- documentação;
- Docker;
- deploy.

Em cada fase, o sistema deve continuar funcionando.

## 22. Deploy

Ao final, sugerir opções simples e baratas para manter o serviço rodando 24/7.

Priorizar opções adequadas para um projeto pessoal/MVP.

Explicar:

- custo aproximado;
- limitações;
- facilidade de deploy;
- persistência do PostgreSQL;
- execução de workers;
- gerenciamento de secrets.

## 23. Resultado esperado

Quero terminar com um sistema que funcione aproximadamente assim:

[Scheduler]
      ↓
[Job Sources]
      ↓
[Normalization]
      ↓
[Deduplication]
      ↓
[Heuristic Filtering]
      ↓
[Scoring]
      ↓
[LLM Classification - opcional]
      ↓
[PostgreSQL]
      ↓
[Notification Service]
      ↓
[Email / Telegram / WhatsApp]

O sistema deve funcionar continuamente e me avisar somente quando houver oportunidades que tenham boa probabilidade de serem relevantes para meu perfil.

Priorize simplicidade, modularidade, baixo custo e facilidade de manutenção.

Não implemente scraping agressivo ou técnicas para contornar mecanismos anti-bot. Quando uma plataforma não oferecer uma forma adequada de acesso, proponha uma alternativa legítima.

Antes de escrever código, apresente:

1. arquitetura;
2. decisões tecnológicas;
3. modelo de dados;
4. fluxo completo;
5. estratégia de scoring;
6. estratégia de coleta;
7. estratégia de notificações;
8. plano de implementação por etapas.

Depois disso, comece pela Fase 1 e forneça o código necessário para executá-la localmente.