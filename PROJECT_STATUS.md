# ESET Incident AI Project Status

Updated: 2026-06-23

## Current State

The first operational version is complete.

Implemented capabilities:

- ESET incident collection through the ESET incident API.
- ESET access token issuance from configured username and password.
- Daily scheduled collection at 10:00 Asia/Seoul through Celery Beat.
- Redis-backed Celery worker execution.
- PostgreSQL persistence for delivery idempotency, approval queue, and collection run history.
- Discord delivery for Low and Medium incidents.
- High and Critical incidents held for human approval.
- Approval and rejection APIs.
- Duplicate Discord notification prevention.
- Collection run success and failure records, including short `error_message` on failure.
- `/health` and `/ready` endpoints.
- Docker Compose healthchecks and restart policy.
- Smoke check script and Makefile operational commands.
- Operational runbooks for collector and Discord delivery failures.
- Knowledge ingestion for `.md` and `.txt` files under `knowledge/`.
- Deterministic local embeddings for offline RAG development.
- Knowledge search API and CLI.
- RAG evidence based local analysis API.
- Automatic Low and Medium Discord notifications now include local RAG analysis summary,
  confidence, evidence coverage, evidence IDs, and immediate action.

## Verified Runtime Flow

Verified manually:

- `GET /health` returns `{"status":"ok"}`.
- `GET /ready` returns database and Redis readiness as `ok`.
- ESET token request succeeds from configured credentials.
- ESET incident collection succeeds.
- Discord delivery succeeds.
- Duplicate incidents are skipped.
- Collection run history is written and readable.
- Knowledge ingest indexes runbook documents.
- Knowledge search returns indexed evidence chunks.
- Analysis API returns root cause, remediation, confidence, evidence coverage, and evidence IDs.
- RAG evidence is attached to analysis after knowledge ingest.

## Important Commands

Start or refresh containers:

```bash
sudo docker compose up -d --build --force-recreate api worker scheduler redis postgres
```

Health and readiness:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Smoke check:

```bash
uv run python scripts/smoke_check.py
make smoke
```

Manual collection:

```bash
sudo docker compose exec worker uv run celery \
  -A eset_incident_ai.infrastructure.queue.celery_app \
  call eset_incident_ai.collect_and_notify_incidents --args='[10]'
```

Collection history:

```bash
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
curl 'http://localhost:8000/api/v1/incidents/collection-runs?limit=5'
```

Approvals:

```bash
curl http://localhost:8000/api/v1/approvals/pending
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/approve
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/reject
```

Knowledge ingest and search:

```bash
sudo docker compose exec api uv run python scripts/ingest_knowledge.py --root knowledge
curl 'http://localhost:8000/api/v1/knowledge/search?query=collector%20failure&limit=5'
```

Analysis:

```bash
curl -X POST http://localhost:8000/api/v1/analyses/run \
  -H "Content-Type: application/json" \
  -d '{
    "incident": {
      "external_id": "incident-1",
      "title": "collector failure on ESET worker",
      "severity": "high",
      "summary": "ESET incident collection task failed"
    },
    "tenant_scope": "default"
  }'
```

## Validation

Latest local validation completed:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=85
uv run bandit -r src
uv run pip-audit
docker compose config --quiet
```

Most recent known result:

- Tests: `77 passed`
- Coverage: `86.94%`
- Bandit: no issues
- pip-audit: no known vulnerabilities

## Security Notes

- Do not commit `.env`.
- Do not print or paste ESET access tokens, refresh tokens, passwords, or Discord webhook URLs.
- The Discord webhook and ESET tokens pasted during development should be considered exposed and rotated.
- Discord notifications are sanitized and should not include raw identifiers.
- High and Critical incidents require human approval before notification or action.

## GitHub Push Blocker

At the time of this status update:

- `/home/devops/project/eset-incident-ai` is not initialized as a Git repository.
- No Git remote is configured.
- GitHub CLI `gh` is not installed in the environment.

To push this project to GitHub, install and authenticate GitHub CLI or provide another
authenticated Git remote workflow, then initialize the repository and add an origin remote.

Example follow-up commands after prerequisites are ready:

```bash
git init
git add .
git commit -m "Implement ESET incident AI operational flow"
git branch -M main
git remote add origin <github-repository-url>
git push -u origin main
```

## Remaining Future Enhancements

- Replace `LocalAnalysisGateway` with OpenAI or Anthropic gateway when provider credentials are ready.
- Expand ESET evidence collection with detections, devices, timelines, and asset context.
- Add more runbooks, ESET guides, internal policies, and MITRE content to `knowledge/`.
- Evaluate analysis quality with curated datasets.
- Harden Kubernetes and Helm deployment manifests for production.
