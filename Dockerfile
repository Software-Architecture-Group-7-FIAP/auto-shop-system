# ==========================================
# Estágio 1: Builder (Instalação e Compilação)
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Instala dependências de compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

ENV POETRY_VERSION=2.4.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-ansi --only main --no-root

# ==========================================
# Estágio 2: Runtime Mínimo e Seguro
# ==========================================
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Instala libpq5 (runtime do Postgres) e curl (para o healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Criação do usuário não-root (Princípio do Menor Privilégio - Cenário 5)
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin appuser

# Copia o ambiente virtual e arquivos estritamente necessários
COPY --from=builder /app/.venv /app/.venv
COPY --chown=10001:10001 src/ ./src
COPY --chown=10001:10001 alembic/ ./alembic
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 pyproject.toml ./

# Muda para o usuário sem privilégios
USER 10001:10001

EXPOSE 8000

# Healthcheck da API (Cenário de Resiliência)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
