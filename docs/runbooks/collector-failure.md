# Collector Failure

Use this runbook when the daily 10:00 KST collection does not create a successful
`collection_runs` record or Discord notifications stop unexpectedly.

## Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
```

Expected healthy readiness:

```json
{"status":"ready","checks":{"database":"ok","redis":"ok"}}
```

If the latest collection run has `status: "failed"`, review `error_message`.
It is intentionally short and must not contain credentials.

## Container Status

```bash
sudo docker compose ps
sudo docker compose logs --tail=120 worker
sudo docker compose logs --tail=120 scheduler
```

The scheduler should show `beat: Starting...` and remain running. The worker
should show the task name `eset_incident_ai.collect_and_notify_incidents`.

## Manual Collection

```bash
sudo docker compose exec worker uv run celery \
  -A eset_incident_ai.infrastructure.queue.celery_app \
  call eset_incident_ai.collect_and_notify_incidents --args='[10]'
```

Then confirm the result:

```bash
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
```

## Common Causes

- `ESET_USERNAME` or `ESET_PASSWORD` missing from `.env`
- `ESET_ACCESS_TOKEN` set to an expired static token instead of being blank
- Redis unhealthy, preventing Celery task delivery
- Postgres unhealthy, preventing idempotency and run history writes
- ESET API authentication or incident endpoint failure

## Safety

- Do not print ESET tokens, passwords, refresh tokens, or Discord webhook URLs.
- Do not paste raw ESET incident payloads into tickets or chat.
- Use `observed_keys` from collection run output for schema troubleshooting.
