# Architecture Review: ESET Detections Ingestion

Date: 2026-06-24
Role: claude / architecture_owner

## Scope

Reviewed codex's implementation against `task-spec.md` and all 30 items in
`acceptance-criteria.md`. Diff adds one new vertical slice (client, entity revision, use cases,
notification builder, two new tables/ports/repositories, Celery task, API routes) plus a shared
`Severity.parse()` generalization and additive-only extensions to four shared DTO files,
`bootstrap.py`, `api/dependencies.py`, `settings/config.py`, and `infrastructure/queue/{tasks,
celery_app}.py`. Full file list verified via `git status --short` / `git diff --stat`, not taken
from codex's self-report.

## 1. Architecture Impact

Compliant. New code follows the existing Hexagonal vertical-slice pattern exactly parallel to the
Incident slice: `EsetDetectionClient` (Infrastructure) -> `CollectAndNotifyDetections`
(Application) -> `Detection`/`Severity` (Domain), with Domain still importing nothing from
FastAPI/SQLAlchemy/LangGraph/Anthropic SDK/OpenAI SDK/Discord SDK. The four shared DTO files
(`approval_dto.py`, `approval_result.py`, `collection_result.py`, `collection_run_dto.py`) and
`bootstrap.py` were touched, but every change is a pure addition (new class or new router
registration) — confirmed line-by-line via `git diff`, no existing class/route/field was modified
or removed. `domain/entities/detection.py` was revised (field rename from
`detection_id/name/process_name/file_hash` to `id/external_id/title/severity/.../user_name/
device_name/normalized_payload`); verified via `grep -rn "Detection("` and grep for the old field
names across `src/`/`tests/` that this entity was never constructed anywhere before this change
(only referenced as an unused `Incident.detections: tuple[Detection, ...]` field) — so this is not
a breaking change to any exercised code path. `Severity.parse()`'s generalization
(`text.split("_level_")[-1]` replacing the old fixed-prefix `removeprefix`) was checked against
`tests/unit/test_normalize_incident.py` and `tests/unit/test_collect_and_notify_incidents.py`,
both independently re-run and passing with no regression.

## 2. Security Impact

Compliant, and this is the part that mattered most for this task. Independently inspected
`infrastructure/discord/detection_notification_builder.py`: the raw-field bypass is implemented as
exactly the named allowlist the threat-assessment required —
`RAW_DETECTION_FIELDS = frozenset({"userName", "device"})` — and only those two fields skip
`Sanitizer.sanitize_text`; `displayName`/`context`/`objectName`/`objectUrl`/`objectHashSha1` all
route through the sanitizer. `tests/unit/test_detection_notification_builder.py` proves this
directly: a fixture with email addresses embedded in `displayName`/`context`/`objectName`/
`objectUrl` plus an `@`-containing `userName` and a Windows-path-looking `device` asserts the
sanitized fields' raw values are absent from the rendered payload while `userName`/`device` survive
verbatim (AC16/17). The footer text ("Detection userName and device fields are shown as-is by
approved policy") accurately states the actual policy rather than reusing Incident's notice
verbatim (AC18) — this was the specific regression called out in the spec
(`llm-anthropic-gateway/threat-assessment.md`'s stale-footer finding) and it does not recur here.
The same allowlist is independently re-implemented (not shared/imported, but identical in content
and intent) in `infrastructure/persistence/detection_approval_repository.py`'s
`RAW_DETECTION_APPROVAL_FIELDS`, so the pending-approval JSONB payload used to rebuild the Discord
message after human review preserves the same raw/sanitized split — without this, the approval-gate
path would have silently masked `userName`/`device` even though the direct-notify path does not,
which would have been an inconsistency worth flagging; it does not exist here.
`Severity.parse()` remains a pure fixed-allowlist string match (no regex, no `eval`), preserving
its existing security property. Independently re-ran `bandit -r src` (no issues) and `pip-audit`
(no known vulnerabilities) — both clean.

## 3. Data Impact

Compliant. `migrations/versions/007_add_detection_tables.py` (`down_revision =
"006_add_collection_run_error_message"`) creates `pending_detection_approvals` (unique
`detection_id`, not `incident_id`) and `detection_collection_runs` (adds `last_page_token TEXT`,
absent from the Incident equivalent). No existing table's schema is touched. `notification_repository`
(`notification_deliveries` table) is reused unmodified for Detection dedup (AC15) — confirmed via
`get_collect_and_notify_detections()` in `dependencies.py` wiring the existing
`PostgresNotificationRepository` directly, no new dedup table created. Approval/collection-run flows
for Incidents and Detections are structurally independent — separate tables, separate repository
classes, separate API routes under `/detections/*` vs `/approvals/*`/`/incidents/*` (AC19-21).

## 4. Operational Impact

New hourly Celery beat entry (`periodic-eset-detection-notification`,
`crontab(minute=f"*/{settings.detection_notify_cron_interval_minutes}")`, default 60) confirmed
non-hardcoded via `tests/unit/test_detection_settings_and_celery.py`. The cursor/backfill design
(`cutoff = now - detection_backfill_window_days`, skip-zone before cutoff, `save_cursor` persisted
per fully-processed page, `save_success` at run end) correctly decouples "records skipped due to
backfill window" from `detection_notify_limit` accounting — independently traced through
`collect_and_notify_detections.py`'s loop logic line-by-line, not just trusted from codex's summary:
pre-cutoff records increment only `skipped_count` and `continue` before reaching the
`processed_count >= limit` check (AC7-9); the per-run page cap (`max_pages_per_run`) is enforced as
the outer `while` condition and the cursor is persisted incrementally as each page completes, so a
capped run still saves forward progress (AC10-11) — confirmed via
`test_collect_detections_stops_at_page_cap_and_persists_cursor` and
`test_collect_detections_persists_cursor_and_resumes_from_latest_token`. No fixed Celery task
timeout was found in `celery_app.py` that would kill a long-running first backfill pass. New
Settings defaults (`detection_notify_limit=500`, `detection_max_pages_per_run=1000`,
`detection_backfill_window_days=30`, `detection_notify_cron_interval_minutes=60`,
`eset_detection_page_size=1000`) match task-spec.md exactly (AC22), confirmed via
`test_detection_settings_defaults_match_spec`.

## 5. Required Tests

All satisfied and independently re-verified (not just trusting codex's self-report):

- `uv run ruff format --check .` -> 169 files already formatted.
- `uv run ruff check .` -> All checks passed.
- `uv run mypy src` -> Success: no issues found in 122 source files.
- `uv run pytest --cov=src --cov-fail-under=85` -> 162 passed, 86.34% coverage (matches codex's
  self-report exactly on independent re-run).
- `uv run bandit -r src` -> No issues identified.
- `uv run pip-audit` -> No known vulnerabilities found.
- Security-gate (gitleaks/semgrep/trivy) — see `security-gate-report.md`: 0 new findings
  attributable to this diff; gate FAILs only on the same pre-existing, already-tracked Dockerfile/
  jinja2/urllib findings documented in `eset-severity-enum-fix/security-gate-report.md`.
- Read every new/changed source file directly (not excerpts from codex's log) for: severity
  generalization, detection client (pagination, unsupported-param guard, retry policy), the
  collect-and-notify use case's full control flow, the notification builder's raw/sanitized split,
  the persistence repository's mirrored allowlist, the migration, the API routes, and the Celery/
  Settings wiring. All 27 automatable acceptance-criteria items (1-27) are demonstrated by a
  passing test or directly observable in source; items 28 is covered by `security-gate-report.md`;
  items 29-30 are manual/post-deployment and not blocking.

## 6. Approval or Rejection

**Approved.** Implementation matches `task-spec.md` and all automatable items in
`acceptance-criteria.md`, stays within the parallel-slice design (no existing Incident table, port,
route, or use case was modified beyond `Severity.parse()`'s internals, whose public contract is
unchanged), and the deterministic-verification suite is fully green on independent re-run. The
security-sensitive raw-`userName`/`device` exception is scoped exactly as authorized — a narrow,
auditable named allowlist, not a blanket sanitizer bypass — applied consistently across both the
direct-notify and approval-then-notify paths. Security-gate findings are pre-existing technical debt
unrelated to this diff and do not block this feature. Proceeding to ask the project owner for
explicit confirmation before commit/push (per `harness.yaml`'s `allow_direct_push: false` and this
project's human-approval-before-irreversible-action practice), then container rebuild and live
verification.
