# Acceptance Criteria: ESET Detections Ingestion

Each item must be demonstrable by a passing automated test unless marked manual.

## Severity Parsing (generalized, shared with Incidents)

1. `Severity.parse()` maps `SEVERITY_LEVEL_LOW/MEDIUM/HIGH/CRITICAL/UNSPECIFIED` (Detections'
   prefix) to the corresponding `Severity` member (`UNSPECIFIED` → `LOW`), exactly as it already
   does for `INCIDENT_SEVERITY_LEVEL_*` (Incidents' prefix).
2. Every existing test case for `INCIDENT_SEVERITY_LEVEL_*` and all short forms (`"low"`,
   `"medium"`, `"high"`, `"critical"`, `"info"`, `"informational"`) continues to pass unchanged —
   no regression in `tests/unit/test_normalize_incident.py` /
   `tests/unit/test_collect_and_notify_incidents.py`.
3. Unknown/garbage/missing/empty input still defaults to `Severity.LOW` and never raises, for both
   prefix families and plain strings.

## Detection Source Client

4. `EsetDetectionClient.iter_detections(page_token=None, page_size=1000)` calls
   `GET {eset_base_url}/v1/detections` and yields each item from the response's detections list as
   a `dict`, following `nextPageToken` across pages until exhausted — structurally mirroring
   `EsetIncidentClient.iter_incidents`.
5. A test asserts the request params sent to ESET **never** include `filter`, `orderBy`, `sortBy`,
   or `sort` — regression guard for the confirmed-unsupported (400) parameters.
6. `429`/`5xx` responses raise `EsetTemporaryApiError` and are retried (same `tenacity` policy as
   `EsetIncidentClient`); `400`/`404`/other 4xx raise `EsetApiError` and are not retried.

## Cursor / Backfill Behavior

7. On cold start (`DetectionCollectionRunRepository.latest()` returns `None` or a run with
   `last_page_token IS NULL`), `CollectAndNotifyDetections` begins from the oldest record (no
   `page_token`) and skips creating any notification, approval row, or dedup row for every
   detection with `occurTime` older than `now - detection_backfill_window_days`. A test with a
   fixture page containing only pre-cutoff records asserts `notifier.send` and
   `approval_repository.save_pending` are never called, and `skipped_count` reflects them.
8. The first detection at or after the cutoff in a run is processed normally (severity-routed,
   notified or queued for approval) — a test with a mixed pre-/post-cutoff fixture page asserts
   only the post-cutoff records are notified/queued.
9. Pre-cutoff (skipped) records do not count against `detection_notify_limit`; only records that
   pass the cutoff and are actually processed (notified or queued for approval) count toward it —
   a test asserts a run with a large all-skipped first page does not stop early due to the limit.
10. After a successful run, the new `nextPageToken` is persisted via
    `DetectionCollectionRunRepository.save_success(..., last_page_token=...)`. A subsequent run
    resumes from that token (a test asserts the second call to `iter_detections` is invoked with
    the previously-persisted `page_token`, not `None`).
11. A run stops when total pages fetched reaches `detection_max_pages_per_run`, even if
    `detection_notify_limit` has not been reached — a test with a fixture source yielding more
    pages than the cap asserts the loop stops at the cap and persists the cursor at that point.

## Severity Routing / Notification

12. A Detection fixture with `severityLevel = "SEVERITY_LEVEL_HIGH"` (or `CRITICAL`) and
    `occurTime >= cutoff` routes to `DetectionApprovalRepository.save_pending`, not
    `notifier.send` — mirrors
    `test_collect_and_notify_routes_real_eset_high_severity_to_pending_approval` for Incidents.
13. A Detection fixture with `severityLevel = "SEVERITY_LEVEL_LOW"` (or `MEDIUM`) and
    `occurTime >= cutoff`, not previously delivered, calls `notifier.send` and then
    `notification_repository.mark_delivered`.
14. A Detection already marked delivered (`notification_repository.was_delivered` returns `True`)
    is skipped (counted as duplicate, not re-sent) on a subsequent run/page.
15. `notification_deliveries` (existing table/port) is reused unmodified for Detection dedup — no
    new notification-dedup table is created.

## Discord Payload — Raw vs. Sanitized Fields (the security-sensitive part of this task)

16. `SanitizedDetectionNotificationBuilder.build()` includes `userName` and `device` in the built
    Discord payload **without** going through `Sanitizer.sanitize_text` — a test constructs a
    Detection with a `userName`/`device` value that would otherwise be altered by the sanitizer
    (e.g., containing an `@`-looking substring or a Windows-path-looking substring) and asserts the
    exact original string appears unmodified in the built payload.
17. The same builder **does** sanitize `displayName`, `context`, `objectName`, and `objectUrl`
    through `Sanitizer.sanitize_text` — a test constructs a Detection with an email address
    embedded in `context` and asserts the built payload does not contain the raw email (same
    pattern as the existing Incident notification builder test).
18. The built payload's footer/notice text accurately reflects the actual policy for Detections
    (i.e., must not reuse Incident's notice text verbatim if it would misrepresent which fields are
    raw vs. masked — see `docs/specs/llm-anthropic-gateway/threat-assessment.md`'s prior finding
    that a stale "Sanitized... raw identifiers are not included" footer claim was false; this must
    not recur here).

## Approval Workflow (parallel to Incidents)

19. `pending_detection_approvals` has a `detection_id` unique column (not `incident_id`) — verified
    by the new migration and `PostgresDetectionApprovalRepository`'s `INSERT ... ON CONFLICT
    (detection_id)`.
20. `GET /detections/pending-approvals`, `POST /detections/pending-approvals/{id}/approve`, and
    `POST /detections/pending-approvals/{id}/reject` work end-to-end against a test database,
    mirroring the existing `/approvals/*` routes' behavior for Incidents.
21. Approving/rejecting a pending Detection approval does not touch `pending_approvals` (Incidents'
    table) and vice versa — the two flows are fully independent.

## Configuration

22. `detection_notify_limit`, `detection_max_pages_per_run`, `detection_backfill_window_days`,
    `detection_notify_cron_interval_minutes`, `eset_detection_page_size` are read from
    environment/`.env` only via `Settings`, with the defaults stated in task-spec.md. None has a
    placeholder/fake-looking default.
23. The new Celery beat entry uses `crontab(minute=f"*/{settings
    .detection_notify_cron_interval_minutes}")`, not a hardcoded interval.

## Testing

24. New unit tests cover: `Severity.parse()` generalization (parametrized, includes both prefix
    families), `EsetDetectionClient` pagination and the filter/sort regression guard, cursor
    persistence and resume, backfill skip-zone exclusion (pre-cutoff vs. post-cutoff), severity
    routing (HIGH/CRITICAL → approval, LOW/MEDIUM → notify), dedup, the raw-vs-sanitized field
    split in the Discord builder (item 16/17 — this is the most important test in the whole suite,
    since it is the only thing standing between this task and a CLAUDE.md violation), and the
    safety-cap on pages-per-run.
25. `uv run pytest --cov=src --cov-fail-under=85` passes including the new code.
26. `uv run mypy src` and `uv run ruff check .` / `uv run ruff format --check .` pass.
27. `uv run bandit -r src` and `uv run pip-audit` pass with no new findings.
28. The project's security-gate stage (gitleaks/semgrep/trivy) reports no new findings attributable
    to this diff (pre-existing unrelated findings, as already documented in
    `docs/specs/eset-severity-enum-fix/security-gate-report.md`, remain acceptable).

## Manual / Operational (not automated)

29. After deployment, a manual check confirms the first real run's `skipped_count` is roughly
    consistent with ~314k records minus ~30 days' worth (order-of-magnitude sanity check, not an
    exact assertion), and that `last_page_token` is non-null afterward.
30. A manual check confirms at least one real HIGH/CRITICAL Detection (if one occurs naturally
    within the verification window) correctly appears in `GET /detections/pending-approvals` with
    raw `userName`/`device` values, before approving/rejecting it.
