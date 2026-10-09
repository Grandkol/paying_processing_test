# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/srv

WORKDIR /srv

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /srv
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
