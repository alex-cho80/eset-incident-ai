FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev || uv pip install -e .

COPY . .
RUN addgroup --system app && \
    adduser --system --ingroup app --home /app app && \
    chown -R app:app /app

USER app
CMD ["uv", "run", "celery", "-A", "eset_incident_ai.infrastructure.queue.celery_app", "worker", "--loglevel=INFO"]
