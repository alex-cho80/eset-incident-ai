# ESET Incident AI Project Status

Updated: 2026-06-25 (Ollama local LLM gateway implemented)

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
- RAG evidence based analysis API.
- Automatic Low and Medium Discord notifications now include RAG analysis summary,
  confidence, evidence coverage, evidence IDs, and immediate action.
- `OllamaGateway`/qwen2.5 removed (project-owner decision, 2026-06-30): the auto-notify
  pipelines (`CollectAndNotifyIncidents`/`CollectAndNotifyDetections`) no longer run any LLM
  analysis step — ESET incident/detection data is sent straight to Discord. The manual
  `/api/v1/analyses/run` endpoint still works, now backed only by the deterministic
  `LocalAnalysisGateway` (no external model call). The `ollama` Docker Compose service,
  `OLLAMA_*`/`LLM_PROVIDER`/`LLM_MODEL`/`LLM_TIMEOUT_SECONDS`/`LLM_MAX_RETRIES` settings, and
  `structured_output.py` were deleted along with it.
- `MIN_NOTIFY_SEVERITY` (default `medium`, 2026-06-30): incidents/detections below this severity
  are skipped entirely — no analysis, no Discord notification, no DB idempotency record.
- IP address pseudonymization removed from the shared sanitizer by explicit project-owner
  decision. Raw private and public IPs now flow to the Discord notification builder and the LLM
  gateway prompt.

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
- Analysis API returns root cause, remediation, confidence, evidence coverage, and evidence IDs
  (via `LocalAnalysisGateway`; no external model call as of 2026-06-30).
- RAG evidence is attached to analysis after knowledge ingest.

Three bugs were found and fixed only by this live verification (spec review alone did not
surface them):

1. `docker compose restart` does not re-read `.env`/`env_file` changes — it just restarts the
   existing container with its old environment. Changing `.env` or code requires
   `sudo docker compose up -d --build <service>`.
2. `LLM_TIMEOUT_SECONDS=30` was too short for the combined root-cause + remediation call (up to
   4096 tokens); it was previously raised to `90` and is now `240` for the CPU-bound local model.
3. The model sometimes wrapped JSON responses in markdown code fences, breaking `json.loads`;
   `structured_output.py` now strips code fences before parsing (`_strip_code_fence`).
4. Evidence-id validation rejected the `no-supporting-evidence` sentinel whenever any evidence
   was retrieved, even if irrelevant to the specific claim. Fixed so the sentinel is always a
   valid id (`{...} | {_NO_EVIDENCE_ID}` in the gateway).

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

- Tests: `179 passed`
- Coverage: `87.29%`
- ruff format: `169 files already formatted`
- ruff check: clean
- mypy: no issues in `122 source files`
- Bandit: no issues, `3888` lines of code scanned
- pip-audit: no known vulnerabilities found
- `docker compose config --quiet`: clean

## Security Notes

- Do not commit `.env`.
- Do not print or paste ESET access tokens, refresh tokens, passwords, or Discord webhook URLs.
- The Discord webhook and ESET tokens pasted during development should be considered exposed and rotated.
- Discord notifications are sanitized and should not include raw identifiers.
- High and Critical incidents require human approval before notification or action.
- **Known open gap (intentionally not fixed yet):** the sanitizer only pseudonymizes emails,
  Windows user-home paths, and `token`/`secret`/`password`/`webhook` key-value pairs. It does
  **not** catch IP addresses, hostnames, or free-text employee identifiers (e.g. a
  branch/name/employee-number string embedded in an ESET `description` field). A real production
  incident was delivered to Discord on 2026-06-23 with such an identifier exposed despite the
  message claiming "Raw identifiers are not included." The user was offered immediate mitigation
  (`DISCORD_ENABLED=false`, sanitizer fix, message deletion) and explicitly declined, choosing to
  accept the risk on that channel for now. Treat this as still open before pointing any new
  Discord channel at this code as-is.
- **Known open gap / project owner decision (2026-06-24):** the project owner explicitly decided
  to stop masking IP addresses in both the Discord notification and LLM prompt paths; both use the
  same shared `Sanitizer`. Raw private and public IP addresses now reach Discord and the local
  Ollama prompt. Email addresses, Windows paths, and `token`/`secret`/`password`/`webhook`
  key-value pairs are still masked.

## GitHub Push

Resolved. The repository is initialized, has an `origin` remote configured over HTTPS (PAT-based
credential helper), and `main` is pushed and up to date:

```bash
git remote -v
# origin  https://github.com/alex-cho80/eset-incident-ai.git (fetch)
# origin  https://github.com/alex-cho80/eset-incident-ai.git (push)
```

Commit history so far:

- `a1f8f89` Initial commit
- `d7c430a` Implement ESET incident AI operational flow
- `9941b11` Add the first real LLM gateway with provider-selection factory

## Remaining Future Enhancements

- Expand ESET evidence collection with detections, devices, timelines, and asset context.
- Add more runbooks, ESET guides, internal policies, and MITRE content to `knowledge/`.
- Evaluate analysis quality with curated datasets.
- Evaluate whether the Incident-vs-Detection analyzer-exception asymmetry should remain under a
  local, single-instance LLM backend.
- Close the sanitizer hostname/employee-identifier gap described above (deferred by user choice,
  not forgotten).

Kubernetes/Helm hardening was explicitly decided against (2026-06-23) — Docker Compose remains
the deployment target for this project.
