# Subindo o docker
docker compose up --build -d

# Iniciando a aplicação(Telegram + LLM)
curl -X POST http://localhost:8000/sources/ingest -> Isso na porta local

# status LLM
curl http://localhost:8000/scoring/llm/status 

# Parando o docker
docker compose down
