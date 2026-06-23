# Discord Delivery Failure

Use this knowledge entry when ESET collection succeeds but Discord does not
receive an expected notification.

Check the latest collection run and pending approval queue:

```bash
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
curl http://localhost:8000/api/v1/approvals/pending
sudo docker compose logs --tail=120 worker
```

If `duplicate_skipped_count` is greater than zero, the system intentionally
suppressed repeated notifications. If `pending_approval_count` is greater than
zero, High or Critical incidents require manual approval before Discord delivery.

Never print or paste the Discord webhook URL. Rotate the webhook if it is exposed.
