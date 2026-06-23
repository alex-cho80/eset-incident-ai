# Collector Failure

Use this knowledge entry when ESET incident collection fails, the worker task does
not complete, or the latest collection run reports `status: failed`.

Check service state:

```bash
curl http://localhost:8000/ready
curl http://localhost:8000/api/v1/incidents/collection-runs/latest
sudo docker compose logs --tail=120 worker
sudo docker compose logs --tail=120 scheduler
```

Common causes include invalid ESET credentials, an expired static access token,
Redis broker failure, Postgres write failure, or ESET API downtime.

Do not print ESET access tokens, refresh tokens, passwords, or raw incident
payloads while troubleshooting.
