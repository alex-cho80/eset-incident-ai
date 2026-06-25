# Task Spec: Remove human-approval gate for HIGH/CRITICAL — auto-analyze and notify like LOW/MEDIUM

## Business Requirement

User decision (2026-06-25, explicit, with the CLAUDE.md conflict called out and acknowledged
before confirming): HIGH/CRITICAL Incidents and Detections should no longer wait for human
approval before reaching Discord. They should be analyzed by the same `AnalyzeIncident`/
`OllamaGateway` path as LOW/MEDIUM and auto-notified the same way. This **reverses** the CLAUDE.md
rule "High and critical incidents require human approval before notification or remediation" —
that rule must be updated as part of this change so the doc matches reality (see "CLAUDE.md
update" below), not left stale.

## Data Flow

No new data sources. Same `EsetIncidentClient`/`EsetDetectionClient` → `CollectAndNotifyIncidents`/
`CollectAndNotifyDetections` → `AnalyzeIncident` (Ollama) → `Sanitizer` → `Notifier` (Discord) path
that LOW/MEDIUM already uses today. The only change is removing the severity branch that diverts
HIGH/CRITICAL into `ApprovalRepository.save_pending`.

## Trust Boundary

Unchanged — ESET payload is still untrusted input, same sanitizer rules apply regardless of
severity (no new exemption being introduced; HIGH/CRITICAL gets exactly the same sanitization
LOW/MEDIUM already gets).

## Code Changes

1. **`src/eset_incident_ai/application/use_cases/collect_and_notify_incidents.py`**
   (`_execute`, lines ~80-115): delete the
   `if severity in {Severity.HIGH, Severity.CRITICAL}: ... else: ...` branch so *every* severity
   takes the path currently reserved for the `else` branch (dedup check → analyze → notify → mark
   delivered). `pending_approval_count` stays in the `IncidentCollectionResult` dataclass (do not
   change its shape) but will now always be `0` from this use case — leave it, don't remove the
   field (other callers/tests may still construct this DTO).
2. **`src/eset_incident_ai/application/use_cases/collect_and_notify_detections.py`**
   (`_execute`, lines ~118-125): same change — delete the HIGH/CRITICAL branch that calls
   `self._approval_repository.save_pending(...)` and `continue`s; let every severity fall through
   to the existing dedup → `_analyze_detection` → notify → mark-delivered block.
3. Both use cases keep their `approval_repository`/`DetectionApprovalRepository` constructor
   parameter (still required — `ReviewPendingApproval`/`ReviewPendingDetectionApproval` and the
   `/pending` list endpoints still use the same repositories for whatever is already in those
   tables; removing the constructor param is out of scope, see "Out of Scope").
4. **`CLAUDE.md`** "Security Rules" section: change
   `High and critical incidents require human approval before notification or remediation.` to
   reflect the new policy (e.g. `All incidents/detections regardless of severity are
   auto-analyzed and auto-notified; there is no pre-notification human-approval gate.`). Leave the
   rest of the Security Rules section (token/PII rules) untouched.

## One-Time Backfill (separate from the code change, run once after deploy)

Confirmed via `GET /api/v1/detections/pending-approvals` (2026-06-25): **0** pending Incident
approvals, **50** pending Detection approvals, all `severity=high`. User decision: bulk-backfill
all 50 — run them through analysis and send to Discord, then clear them from the pending queue
(do not leave them stuck, do not silently drop them un-notified).

- Write a one-off script (e.g. `scripts/backfill_pending_detection_approvals.py`, run manually
  inside the worker/api container after deploy — not wired into any deploy step or cron) that:
  1. Lists all rows with `status="pending"` via `DetectionApprovalRepository` (reuse whatever
     listing method backs `GET /pending-approvals`).
  2. For each: build the analysis `Incident` adapter from `approval.payload` (same
     mapping `CollectAndNotifyDetections._to_analysis_incident` does — duplicate the small mapping
     here rather than refactor that private method into a shared util; this project's existing
     convention already duplicates small per-file mapping helpers, e.g. the `context` fallback
     chain in `detection_notification_builder.py`/`detection_approval_repository.py`).
  3. Run `AnalyzeIncident.execute()`, same as the live path (catch+log+continue with
     `analysis=None` on failure, matching `collect_and_notify_detections.py`'s existing per-record
     resilience pattern — do not let one bad analysis abort the whole backfill).
  4. Dedup-check + send via the same `notification_builder.build(payload, analysis)` →
     `Notifier.send()` → `NotificationRepository.mark_delivered()` sequence already used elsewhere.
  5. `DetectionApprovalRepository.mark_reviewed(approval_id, status="approved")` to clear it from
     the pending queue.
  6. Log progress per item (approval_id, detection_id, success/failure) — this will take a while
     (see Operational impact below), a human should be able to tell it's progressing, not hung.
- Idempotent re-run safety: if the script is interrupted and re-run, already-`mark_reviewed`
  rows must not be re-processed (filter by `status="pending"` each time covers this), and
  already-delivered Discord messages must not be re-sent (existing `was_delivered` idempotency
  key check covers this).

## Operational Impact (flag this to the user before running the backfill)

Ollama is configured `OLLAMA_NUM_PARALLEL=1` (single concurrent generation) and the benchmarked
per-call latency is ~150-180s. Sequentially analyzing 50 detections will take roughly **2-2.5
hours** end-to-end, with Discord messages trickling in at that pace (not a sudden burst — this
naturally self-throttles, unlike the earlier 30-day backlog-drain incident). Run it in a way that
survives the terminal/session closing (e.g. `nohup`/inside the container with `docker compose
exec -d`, or as a detached process), and check progress via its log rather than waiting
synchronously.

## Failure Scenarios

- Ollama analysis fails for a given detection mid-backfill → log and continue with
  `analysis=None`, still send+mark-reviewed (matches live-path resilience decision from
  [[project-eset-incident-ai]] "Incident/Detection 예외처리 비대칭 결정" — per-record catch, don't
  abort the batch).
- Discord webhook call fails (network/4xx/5xx) → do **not** call `mark_reviewed` for that item
  (leave it `pending` so a re-run retries it); do not mark `mark_delivered` either.
- Script crashes/killed mid-run → safe to re-run from scratch (idempotent per item, see above).

## Acceptance Criteria

1. Fixture incident/detection with `severity=HIGH` (and `CRITICAL` where the enum allows it)
   passed into `CollectAndNotifyIncidents`/`CollectAndNotifyDetections` now lands in
   `notified_count`, not `pending_approval_count` — update/replace the existing tests that assert
   the opposite (`test_collect_and_notify_incidents.py`, `test_collect_and_notify_detections.py`
   currently assert HIGH/CRITICAL routes to `approval_repository.save_pending`; these assertions
   must flip).
2. LOW/MEDIUM behavior is provably unchanged (regression-guard: existing LOW/MEDIUM tests still
   pass unmodified).
3. `CLAUDE.md` Security Rules section reflects the new no-approval-gate policy — text must not
   contradict actual code behavior.
4. Backfill script: dry-run-able count check (`SELECT count(*) WHERE status='pending'` equivalent
   via the repository) before actually sending; after a full run, `GET
   /api/v1/detections/pending-approvals` returns `[]` (or only rows that genuinely failed and were
   left `pending` for retry, with those failures visible in its log).
5. Full deterministic-verification suite still passes (`ruff`, `mypy`, `pytest`
   `--cov-fail-under=85`, `bandit`, `pip-audit`).

## Security Requirements

- No change to what gets sanitized or how (`Sanitizer.sanitize_text`, raw IP/hostname/userName
  policy) — this spec only changes the severity-based *routing*, not the PII/sanitization rules.
- Backfill script must not log Discord webhook URL or any secret (same rule as the rest of the
  codebase).

## Test Strategy

- Update the two existing use-case tests noted in Acceptance Criteria #1.
- Add a unit test for the backfill script's per-item mapping function (payload → `Incident`
  adapter) mirroring the existing `_to_analysis_incident` tests.
- Full deterministic-verification chain (see Acceptance Criteria #5).

## Out of Scope

- Removing the now-unused-at-this-call-site `approval_repository` constructor parameter, the
  `pending_approval_count` field, the `/pending` review API endpoints, or the
  `pending_approvals`/`pending_detection_approvals` tables themselves — they remain valid for
  whatever historical rows exist and as a manual-review escape hatch; ripping them out is a
  separate cleanup task, not requested here.
- Any change to Incident-side pending approvals — confirmed 0 rows exist, so no backfill needed
  there, only the code-path change applies.
- Any change to LOW/MEDIUM behavior, sanitization rules, or the Ollama model/config.
