FROM python:3.12-slim

WORKDIR /app

# uv para instalação rápida
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# Dependências do sistema (psycopg precisa de libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia manifestos primeiro para cache
COPY pyproject.toml README.md ./
COPY app ./app
COPY config ./config
COPY migrations ./migrations
COPY alembic.ini ./

RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
