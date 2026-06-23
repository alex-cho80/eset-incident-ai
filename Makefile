DOCKER ?= docker
COMPOSE ?= $(DOCKER) compose

.PHONY: install format lint type test security verify smoke ingest-knowledge search-knowledge compose-up compose-ps compose-logs-api compose-logs-worker compose-logs-scheduler collect-now dev

install:
	uv sync --all-extras

format:
	uv run ruff format .

lint:
	uv run ruff check .

type:
	uv run mypy src

test:
	uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=85

security:
	uv run bandit -r src
	uv run pip-audit

verify:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy src
	uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=85
	uv run bandit -r src
	uv run pip-audit

smoke:
	uv run python scripts/smoke_check.py

ingest-knowledge:
	uv run python scripts/ingest_knowledge.py --root knowledge

search-knowledge:
	uv run python scripts/search_knowledge.py "$(QUERY)"

compose-up:
	$(COMPOSE) up -d --build --force-recreate api worker scheduler redis postgres

compose-ps:
	$(COMPOSE) ps

compose-logs-api:
	$(COMPOSE) logs --tail=120 api

compose-logs-worker:
	$(COMPOSE) logs --tail=120 worker

compose-logs-scheduler:
	$(COMPOSE) logs --tail=120 scheduler

collect-now:
	$(COMPOSE) exec worker uv run celery -A eset_incident_ai.infrastructure.queue.celery_app call eset_incident_ai.collect_and_notify_incidents --args='[10]'

dev:
	uv run uvicorn eset_incident_ai.main:app --reload --host 0.0.0.0 --port 8000
