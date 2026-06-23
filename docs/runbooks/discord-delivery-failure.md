# Discord Delivery Failure

Use this runbook when collection succeeds but Discord does not receive expected
notifications.

## Checks

```bash
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
curl http://localhost:8000/api/v1/approvals/pending
sudo docker compose logs --tail=120 worker
```

Interpretation:

- `notified_count > 0`: worker attempted Discord delivery.
- `duplicate_skipped_count > 0`: notification was intentionally suppressed.
- `pending_approval_count > 0`: High/Critical incidents are waiting for approval.
- `status: "failed"`: review `error_message` and worker logs.

## Approval Flow

High/Critical incidents are not sent to Discord automatically.

```bash
curl http://localhost:8000/api/v1/approvals/pending
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/approve
curl -X POST http://localhost:8000/api/v1/approvals/{approval_id}/reject
```

Approval sends only sanitized payload fields and then marks the approval reviewed.

## Manual Collection

```bash
sudo docker compose exec worker uv run celery \
  -A eset_incident_ai.infrastructure.queue.celery_app \
  call eset_incident_ai.collect_and_notify_incidents --args='[10]'
```

## Safety

- Never print or paste the Discord webhook URL.
- Never disable duplicate protection to force a repeat message.
- For test messages, rotate the webhook after external sharing or accidental paste.
- If delivery remains failed, keep High/Critical items pending manual review.
