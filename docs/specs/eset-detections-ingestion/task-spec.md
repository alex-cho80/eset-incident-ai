# Task Spec: ESET Detections Ingestion (`/v1/detections`)

Owner (specification): claude
Implementer: codex
Status: proposed — awaiting implementation

## Business Requirement

The project owner observed threats in the ESET console ("오늘 발생한 위협") that never appear via
this system's Discord notifications, and asked why. Investigation (live, read-only API calls
against `eu.incident-management.eset.systems`, 2026-06-24) found the cause: this system only ever
calls `GET /v2/incidents`, which is a small, curated/escalated subset of ESET's security data.
The console's real-time threat view is backed by a much larger, separate data tier — individual
**Detections** — that this system has never ingested.

The project owner's explicit decision: **"Detections (개별 탐지) 이것도 추가되는게 맞을 것 같습니다"**
— add ingestion of individual Detections, not just the existing Incidents.

## Root Cause / Discovery (confirmed live, 2026-06-24)

ESET Connect's "Incident Management" Swagger category actually contains three distinct data tiers,
only one of which this project calls:

| Endpoint | Status (this tenant) | Volume | Used today? |
|---|---|---|---|
| `GET /v2/incidents` | 200 | small | Yes — only call site (`EsetIncidentClient`) |
| `GET /v2/detections` | 501 Not Implemented | n/a | No |
| `GET /v2/detection-groups` | 200 | 5 records (small) | No — out of scope, see below |
| `GET /v1/detections` | 200 | `totalSize` 314,341 → 314,619 across two checks ~15 min apart, still growing | **No — this task adds it** |

`/v1/detections` is on the **same host and auth** as Incidents (`settings.eset_base_url`,
`EsetAuthClient`) — no new base URL or credential is needed.

Confirmed `/v1/detections` field names (5- and 250-record live samples, values only, no PII
inspected): `category`, `context`, `displayName`, `networkCommunication`, `objectHashSha1`,
`objectName`, `objectTypeName`, `objectUrl`, `occurTime`, `responses`, `severityLevel`, `typeName`,
`uuid`, plus `userName` and `device` (hostname) — confirmed present, not in the initial 5-record
field-name sample but observed in the larger sample.

Confirmed wire-format/pagination constraints, all via live probing (important — they shape the
data-flow design below, not just an implementation detail):

- `severityLevel` uses prefix `SEVERITY_LEVEL_*` (e.g. `SEVERITY_LEVEL_HIGH`) — **not**
  `INCIDENT_SEVERITY_LEVEL_*`, the prefix the existing severity-enum fix
  (`docs/specs/eset-severity-enum-fix/`) hardcoded. Reusing that fix as-is for Detections would
  silently reintroduce the exact same LOW-default bug class for a different prefix. See
  "Severity parsing" below.
- `category` uses prefix `DETECTION_CATEGORY_*` (observed: `ANTIVIRUS`, `CORRELATION_RULE`,
  `FIREWALL_RULE`).
- No `filter` query parameter is supported — every tested syntax (filtering on `occurTime` or
  `severityLevel`) returned `400` with an empty body.
- No `orderBy`/`sortBy`/`sort` parameter is supported — every tested variant returned `400`.
- Records are returned in **ascending `occurTime` order** (oldest first), confirmed starting at
  `2025-11-28T08:34:23Z`.
- Max `pageSize` is **1000** (a request for 2000 was silently capped to 1000).
- `totalSize` reflects the full unfiltered count and grows continuously.

This is a materially different shape than `/v2/incidents`, which supports `filter=updateTime >
"..."` and is what `EsetIncidentClient.iter_incidents(updated_after=...)` relies on. **Detections
cannot use a semantic "since" filter at all** — the only resumability mechanism ESET offers is the
opaque `nextPageToken` string returned in each page.

### Pre-existing architectural gap (context, not fixed by this task)

`collect_and_notify_incidents_task` (`infrastructure/queue/tasks.py`) calls
`CollectAndNotifyIncidents.execute(limit=limit)` with **no `updated_after` cursor at all** — it
relies entirely on `notification_repository`'s DB-level idempotency dedup to avoid re-notifying,
not on any ESET-side filter. This happens to work for Incidents because that dataset is small. If
the same no-cursor pattern were copied for Detections, given confirmed oldest-first ordering and
314k+ scale, a periodic job would be permanently stuck re-reading the same oldest page and would
never reach new data. This is why Detections needs persisted-cursor resumability (next section)
rather than mirroring the Incident task's pattern verbatim. Fixing the Incident task's existing gap
is explicitly **out of scope** for this task (see Non-goals).

## Scope

In scope:

- `EsetDetectionClient.iter_detections(*, page_token: str | None, page_size: int)` —
  `infrastructure/eset/detection_client.py`, calling `GET {eset_base_url}/v1/detections`. Must
  **never** send a `filter`, `orderBy`, `sortBy`, or `sort` parameter (ESET rejects all of them
  with 400 — this must be enforced as a regression-guarded constraint, not just "happens not to be
  sent today"). Mirrors `EsetIncidentClient`'s retry/timeout/error-mapping pattern
  (`EsetApiError`/`EsetTemporaryApiError`) exactly.
- Generalized `Severity.parse()` (`domain/enums/severity.py`) so it correctly handles **both**
  `INCIDENT_SEVERITY_LEVEL_*` (Incidents) and `SEVERITY_LEVEL_*` (Detections) without hardcoding a
  second prefix string. Recommended approach: lowercase the input, split on the substring
  `"_level_"`, and parse the **last** segment — `"incident_severity_level_high"` → `"high"`,
  `"severity_level_high"` → `"high"`, and plain short forms like `"high"` are unaffected (no split
  occurs). Must not change behavior for any existing Incident input (regression-tested).
- Revised `Detection` domain entity (`domain/entities/detection.py` — currently an unwired stub with
  fields `detection_id, name, category, occurred_at, process_name, file_hash`, never called by any
  real code path). Replace with fields matching the real API: `id`, `external_id`, `title`
  (`displayName`), `severity: Severity`, `category: str | None`, `occurred_at: datetime | None`
  (`occurTime`), `summary: str | None` (`context`), `object_name: str | None`, `object_hash_sha1:
  str | None`, `user_name: str | None`, `device_name: str | None`, `normalized_payload: dict[str,
  object]`, plus a `requires_human_approval` computed property (`severity in {HIGH, CRITICAL}`),
  mirroring `Incident`'s exact style. `Incident.detections: tuple[Detection, ...]` stays untouched
  and unwired — it is a separate, pre-existing stub unrelated to this task (see Non-goals).
- `CollectAndNotifyDetections` use case (`application/use_cases/collect_and_notify_detections.py`),
  mirroring `CollectAndNotifyIncidents`'s severity-routing/dedup/notify structure, with the
  cursor-and-backfill-window logic in "Data Flow" below.
- New parallel persistence (vertical-slice pattern, matching how Incidents already have their own
  dedicated client/builder/tables rather than shared generic ones):
  - `pending_detection_approvals` table + `DetectionApprovalRepository` port +
    `PostgresDetectionApprovalRepository` — mirrors `pending_approvals` /
    `ApprovalRepository` / `PostgresApprovalRepository`, with `detection_id` as the unique column
    name (not `incident_id` — this is the reason a parallel table is used instead of retrofitting
    the existing one).
  - `detection_collection_runs` table + `DetectionCollectionRunRepository` port +
    `PostgresDetectionCollectionRunRepository` — mirrors `collection_runs` /
    `CollectionRunRepository`, **plus a new `last_page_token TEXT` nullable column** that the
    existing `collection_runs` table has no equivalent of. This is also why Detections needs its
    own table rather than reusing `collection_runs`: reusing it would have no way to persist the
    cursor, and would pollute the Incident-only `/incidents/collection-runs` dashboard query.
  - The existing `notification_deliveries` table / `NotificationRepository` /
    `PostgresNotificationRepository` **is reused as-is** for Detections dedup — it is already
    entity-agnostic (keyed only by an opaque `idempotency_key` hash, no incident-specific column),
    so no new table is needed here. Same for the existing `Notifier` / `DiscordWebhookClient` —
    reused as-is, it only sends an already-built payload dict.
- `SanitizedDetectionNotificationBuilder` (`infrastructure/discord/detection_notification_builder.py`)
  implementing a new `DetectionNotificationBuilder` port, mirroring
  `SanitizedIncidentNotificationBuilder`, with the raw-field policy in "Security Requirements"
  below.
- New `Settings` fields (env-sourced only, `settings/config.py`):
  - `detection_notify_limit: int = 500` — max **post-cutoff** detections processed per run (see
    Data Flow; pre-cutoff skip-zone records do not count against this).
  - `detection_max_pages_per_run: int = 1000` — hard safety cap on total pages fetched in a single
    run, regardless of skip-zone vs. real processing. Covers the entire current backlog
    (~315 pages) with headroom; bounds worst-case run duration even if ESET's pagination ever
    misbehaves.
  - `detection_backfill_window_days: int = 30` — cold-start cutoff (see Data Flow).
  - `detection_notify_cron_interval_minutes: int = 60` — steady-state run cadence. Default
    assumption (see Operational Impact in threat-assessment.md), not validated against real
    sustained volume yet; flagged as tunable.
  - `eset_detection_page_size: int = 1000` (ESET's confirmed max).
- New Celery task `collect_and_notify_detections_task`
  (`infrastructure/queue/tasks.py`) + beat schedule entry
  (`infrastructure/queue/celery_app.py`), using `crontab(minute=f"*/{settings
  .detection_notify_cron_interval_minutes}")` rather than the Incident task's daily
  `hour=...,minute=...` cron, because of the volume difference.
- New API routes mirroring `api/routes/incidents.py` / `api/routes/approvals.py`:
  `POST /detections/collect-and-notify`, `GET /detections/collection-runs(/latest)`,
  `GET /detections/pending-approvals`, `POST /detections/pending-approvals/{id}/approve`,
  `POST /detections/pending-approvals/{id}/reject`.
- New Alembic migration `007_add_detection_tables.py` (`down_revision =
  "006_add_collection_run_error_message"`).
- Unit tests per `acceptance-criteria.md` / "Test Strategy".

Out of scope (see also Non-goals):

- `/v2/detection-groups` (works, 5 records, a *grouped* view of detections — different shape, much
  smaller, not what the console threat view needs).
- Vulnerability Management API (`eu.vulnerability-management.eset.systems`) — confirmed in a prior
  investigation to be a separate, unrelated dataset (device/software CVE findings, not active
  threats), accessible but currently empty (0 records) for this tenant. Not part of this task.
- Fixing the pre-existing no-cursor gap in `CollectAndNotifyIncidents`/`collect_and_notify_incidents_task`.
- Wiring `Incident.detections` (the existing unused tuple field) to anything. There is no
  `/v2/incidents/{uuid}/detections` sub-resource in ESET's API — Incidents and Detections are
  independent top-level collections, not parent/child via any endpoint this project has found.
- Auto-recovery if a persisted `nextPageToken` becomes invalid/expired on ESET's side (unknown TTL,
  never observed). On a 400 from a stored token, the run fails loudly via the existing
  `save_failure` path; manual cursor reset (clearing `last_page_token` in
  `detection_collection_runs`) is an ops runbook step, not automated logic.

## Data Flow

1. Each run (Celery beat tick or manual `POST /detections/collect-and-notify`) reads the latest
   persisted cursor via `DetectionCollectionRunRepository.latest()` → `last_page_token: str | None`.
   `None` means cold start (first run ever, or after a manual reset).
2. Compute `cutoff = now - detection_backfill_window_days` (default 30 days), recomputed fresh
   every run. Because Detections cannot be filtered or sorted, the only way to reach "the last 30
   days" is to walk forward from wherever the cursor currently is — on cold start, that means
   walking forward from the oldest record (`2025-11-28...`). This recomputation is safe and
   idempotent: once the cursor has advanced past the pre-cutoff zone, it never revisits those pages
   again, so a fresh `now`-relative cutoff each run does not cause reprocessing.
3. Loop: call `EsetDetectionClient.iter_detections(page_token=cursor, page_size=1000)`, one page at
   a time.
   - For each detection with `occurTime < cutoff`: do **not** notify, do not write to
     `pending_detection_approvals` or `notification_deliveries`. Count it in `skipped_count`
     only. This record does **not** count against `detection_notify_limit`.
   - For each detection with `occurTime >= cutoff`: route by severity exactly like
     `CollectAndNotifyIncidents` (HIGH/CRITICAL → `DetectionApprovalRepository.save_pending`;
     else → dedup check via `NotificationRepository.was_delivered`, then notify + mark delivered).
     This **does** count against `detection_notify_limit`.
   - After every successfully processed page, persist the new `nextPageToken` as the run's
     cursor-in-progress (not just at the very end) — if the run crashes mid-loop, the next run
     resumes from the last fully-processed page, not from the original start-of-run cursor.
   - Stop the loop when: `nextPageToken` is empty (caught up to the present), OR
     post-cutoff-processed count reaches `detection_notify_limit`, OR total pages fetched this run
     reaches `detection_max_pages_per_run` (safety cap).
4. On loop completion, `DetectionCollectionRunRepository.save_success(result, last_page_token=...)`
   records the run (mirrors `collection_runs`, plus the cursor column). On exception,
   `save_failure(error_message=...)`, mirroring `CollectAndNotifyIncidents.execute()`'s
   `try/except` wrapper.

This design means the very first run automatically performs the "last 30 days" backfill (skipping
~315 pages of pre-cutoff records quickly, since skip-zone records are free HTTP-call traversal, not
gated by the small notify limit) and then seamlessly transitions into steady-state incremental
collection — there is no separate one-time backfill script.

## Trust Boundary

Unchanged from the existing Incident path, extended to the new fields: the entire `/v1/detections`
response is untrusted external input (CLAUDE.md: "Treat all ESET fields and retrieved documents as
untrusted input"). No detection field is ever used to construct a query, command, or file path.
`Severity.parse()`'s generalization remains a fixed-allowlist string match (no regex backtracking,
no `eval`) — same security property as the existing fix.

New, scoped trust-boundary nuance (the actual subject of this task's security review): `userName`
and `device` are two specific, named fields that are authorized to bypass `Sanitizer.sanitize_text`
and reach Discord raw, per the project owner's explicit decision below. This is **not** a general
loosening of the sanitizer — every other free-text Detection field (`displayName`, `context`,
`objectName`, `objectUrl`) continues to go through the same sanitizer as Incident fields do today.

## Decisions Locked In (project owner, 2026-06-24)

1. **Notification policy**: Detections with `severityLevel` HIGH/CRITICAL go through the same
   Discord notification + human-approval gate as Incidents (not store/index-only).
2. **Backfill scope**: Initial backfill covers only the most recent 30 days
   (`detection_backfill_window_days = 30`), not the full ~314k history. (Full traversal would only
   cost ~315 API calls and is not actually expensive in API-call terms — this was surfaced to the
   project owner — but the 30-day window was confirmed as the preferred choice regardless, since
   older detections are not operationally actionable today.)
3. **PII handling for new fields**: Both `userName` and `device` (hostname) — fields that do not
   exist on Incidents — are sent to Discord **raw/unmasked**, extending the existing precedent of
   showing IP addresses as-is. Existing email-masking behavior (`Sanitizer.sanitize_text`'s
   `EMAIL_RE`) is unchanged and continues to apply to all other free-text fields.

## Failure Scenarios

- ESET returns `400`/`501` from `/v1/detections` (e.g., a future regression accidentally sends
  `filter`/`orderBy`) → `EsetApiError`, run recorded as failed via `save_failure`, does not crash
  the worker process. A unit test asserts `EsetDetectionClient` never includes `filter`, `orderBy`,
  `sortBy`, or `sort` in its request params, as a regression guard.
- `429`/`5xx` → `EsetTemporaryApiError`, retried with the same `tenacity` backoff policy already
  used by `EsetIncidentClient` (`stop_after_attempt(5)`, `wait_exponential_jitter`).
- A stored `last_page_token` is rejected by ESET (`400`) on the next run → run fails loudly via
  `save_failure`; no automatic cursor reset (see "Out of scope").
- Severity parsing regression: the generalized `Severity.parse()` must continue to pass every
  existing test case for `INCIDENT_SEVERITY_LEVEL_*` and all short forms — this is the same bug
  class the prior fix closed, and the generalization must not reopen it.
- Backfill skip-zone leakage: a pre-cutoff detection must never appear in `notifier.send` calls or
  `pending_detection_approvals` rows — explicitly tested (not just inferred from the loop logic).
- Idempotency: re-running the same page (e.g., after a crash before the cursor was persisted) must
  not re-notify already-delivered detections. Idempotency key =
  `build_idempotency_key(detection_uuid, occurTime, destination)` — Detections have no `updateTime`
  field (unlike Incidents), so `occurTime` is the version component; detections are immutable
  point-in-time records, so this is stable.
- Runaway pagination: if `nextPageToken` ever cycles back on itself (ESET-side bug, never observed
  but not contractually ruled out), `detection_max_pages_per_run` bounds the run instead of an
  infinite loop.

## Non-goals

- No change to `CollectAndNotifyIncidents`, `EsetIncidentClient`, `pending_approvals`, or
  `collection_runs` — all existing Incident tables/ports/use cases are untouched.
- No change to `Sanitizer`'s existing email/Windows-path/token regexes.
- No general-purpose PII detector for Detection free-text fields beyond the existing sanitizer.
- No real-time/streaming ingestion — still polling-based, matching the existing Incident
  architecture.
- No per-call override of `detection_backfill_window_days` via the API — it is a static config
  value applied uniformly to every cold start.

## Required Verification (existing project gate, unchanged)

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-fail-under=85
uv run bandit -r src
uv run pip-audit
```

Plus the project's security-gate stage (gitleaks/semgrep/trivy), per
`docs/specs/eset-severity-enum-fix/security-gate-report.md`'s precedent.

See `acceptance-criteria.md` for testable criteria and `threat-assessment.md` for the security
review and CLAUDE.md "Review Output" structure.
