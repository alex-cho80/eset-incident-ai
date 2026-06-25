# Implementation Report

## Changes

- Removed the HIGH/CRITICAL approval diversion in incident collection; all incident severities now use the existing duplicate-check, analysis, notify, and mark-delivered path.
- Removed the HIGH/CRITICAL approval diversion in detection collection; all detection severities now fall through to duplicate-check, analysis, notify, and mark-delivered.
- Kept the approval repository constructor parameters and result DTO `pending_approval_count` fields in place. These counts now remain `0` for the collection use cases.
- Updated `CLAUDE.md` Security Rules to state that incidents/detections are auto-analyzed and auto-notified without a pre-notification approval gate.
- Added `scripts/backfill_pending_detection_approvals.py` for one-time manual processing of pending detection approvals. It supports `--dry-run`, checks delivery idempotency before sending, continues without analysis if analysis fails, and only marks an approval reviewed after duplicate detection or successful delivery.
- Updated incident/detection tests to assert HIGH/CRITICAL notifications instead of pending approvals.
- Added a unit test for the backfill script payload-to-`Incident` mapping function.

## Verification

- `uv run ruff format --check .` passed.
- `uv run ruff check .` passed.
- `uv run mypy src` passed.
- `uv run pytest --cov=src --cov-fail-under=85` passed: 183 passed, total coverage 87.28%.
- `uv run bandit -r src` passed: no issues identified.
- `uv run pip-audit` was run but could not complete in this sandbox because DNS resolution for `pypi.org` failed.

Note: verification was run with `UV_CACHE_DIR=/tmp/uv-cache` because the sandbox cannot write to the default uv cache path.

## Backfill Invocation

Dry-run count check:

```bash
docker compose exec api python -m scripts.backfill_pending_detection_approvals --dry-run
```

Actual backfill:

```bash
docker compose exec api python -m scripts.backfill_pending_detection_approvals
```

Detached run for the expected multi-hour processing window:

```bash
docker compose exec -d api python -m scripts.backfill_pending_detection_approvals
```
