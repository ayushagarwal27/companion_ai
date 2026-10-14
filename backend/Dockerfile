# Build context is the repo root (so `backend` is importable as a package).
# docker-compose.yml points here via build.dockerfile.
FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# psycopg (pulled in by langgraph-checkpoint-postgres) loads libpq at runtime
# via ctypes; python:3.12-slim doesn't ship it.
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies first, separately from app code, so code-only changes
# don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY backend ./backend

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "backend.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
