FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
EXPOSE 8000
