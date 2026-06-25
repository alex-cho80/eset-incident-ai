# Task Spec: Make Incident analysis failures non-fatal (align with Detection's per-record catch)

## Business Requirement

Today, `CollectAndNotifyIncidents._execute()` lets an LLM analyzer exception propagate uncaught,
aborting the *entire* collection run — every Low/Medium incident in that batch, not just the one
that failed analysis. This is Option B from
`docs/specs/eset-local-llm-gateway/threat-assessment.md`'s "Decision required" section: align
Incidents with Detections' already-proven per-record catch, so one bad analyzer call only costs
that one incident its analysis content, not the whole batch. Decided by the project owner
2026-06-25, after the LLM backend moved from Anthropic (SLA'd third-party API) to a single-instance,
no-failover, self-hosted Ollama container with materially less availability guarantee.

## Root Cause / Current Behavior

- `collect_and_notify_incidents.py:91-96`: `analysis = await self._analyzer.execute(...)` inside the
  per-incident loop, with no surrounding `try`/`except`. An exception here propagates out of
  `_execute()`.
- `collect_and_notify_incidents.py:50-57` (the outer `execute()`): catches that exception only to
  call `self._collection_run_repository.save_failure(error_message=...)`, then re-raises. Net
  effect: the run is recorded as failed *and* the caller still sees the exception (a Celery task
  failure, or a 500 if ever called synchronously).
- Contrast with `collect_and_notify_detections.py:186-204`'s `_analyze_detection()`, which wraps the
  equivalent call in `try`/`except Exception`, logs a warning via
  `logger.warning(..., extra={"detection_id": ...}, exc_info=True)`, and returns `None`. The caller's
  loop continues normally with `analysis=None`.
- This asymmetry was an intentional, accepted design choice while the backend was Anthropic. It is
  judged a materially bigger risk now (see `eset-local-llm-gateway/threat-assessment.md`) — this
  task is that decision's implementation.

## Data Flow

No change. Same `AnalyzeIncident.execute()` call through the same `LlmGateway.analyze()` port. Only
the exception handling immediately around that one call changes.

## Trust Boundary

Unchanged — no new external call, no new data egress, no new untrusted input.

## Failure Scenarios

- Analyzer raises for any reason (Ollama unavailable, timeout, validation retries exhausted) on a
  Low/Medium incident → that incident is still collected, sanitized, and notified to Discord with
  `analysis=None`, exactly like a Detection today. The collection run is **not** recorded as a
  failure on account of this, and `_execute()` does not abort.
- High/Critical incidents are unaffected either way: they are routed to
  `approval_repository.save_pending` *before* the analyzer is ever called
  (`collect_and_notify_incidents.py:77-83`) — this task has no effect on the approval-gated path.
- A failure that is **not** the analyzer call (e.g. the ESET source iterator raising, or
  `notification_repository`/`notifier` raising) must continue to abort the run and record a
  collection-run failure exactly as today. The new `except` must wrap only the analyzer call, not
  the rest of the loop body — this task narrows nothing else's fail-closed behavior.

## Acceptance Criteria

1. An analyzer exception while processing one Low/Medium incident does not prevent later incidents
   in the same `_execute()` iteration from being collected and notified.
2. The notification built for that incident is built with `analysis=None`, the same shape
   `SanitizedIncidentNotificationBuilder.build()` already accepts for the Detection path today —
   no signature change needed if so, confirm by inspection first.
3. `collected_count`/`notified_count` still increment correctly for the affected incident;
   `IncidentCollectionResult` is not marked failed and `collection_run_repository.save_failure()` is
   not called on account of the analyzer exception alone.
4. A non-analyzer exception (e.g. the incident source iterator raising) still propagates out of
   `_execute()` and is still recorded via `collection_run_repository.save_failure()` exactly as
   today — regression guard, must have its own test.
5. High/Critical routing (`approval_repository.save_pending`) is untouched and still happens before
   any analyzer call — confirm via `git diff` that those lines are not part of this change.
6. A warning is logged on analyzer failure, including the incident's `external_id` (or equivalent
   identifier) but not its sanitizer-protected `title`/`summary` — match
   `_analyze_detection`'s logging pattern (`extra={...}, exc_info=True`), not a new one.

## Security Requirements

- The new `except` clause must wrap only the analyzer call, not the loop body around it — verify by
  inspection that a `notifier.send()` or `notification_repository.mark_delivered()` failure still
  propagates and still aborts the run.
- No new data leaves the system. The log message on analyzer failure must not include raw
  `incident.summary`/`title` — identifier-only logging, same restriction `_analyze_detection`
  already follows.

## Test Strategy

- Unit test: a fake analyzer raises on the first of two Low/Medium incidents in a fixture batch →
  assert both incidents were notified, the run is not marked failed, and the second incident's
  notification carries a normal (non-`None`) analysis while the first's is `None`.
- Unit test: a fake incident source itself raises → assert the run is still recorded as a failure
  (regression guard for AC4 — this is the most important test in this task, since it's the one that
  proves the fix didn't overreach).
- Full existing deterministic-verification suite must still pass:
  `ruff format --check .`, `ruff check .`, `mypy src`, `pytest --cov=src --cov-fail-under=85`,
  `bandit -r src`, `pip-audit`.

## Out of Scope

- Any change to `collect_and_notify_detections.py` — it already has this behavior; this task makes
  Incidents match it, not the reverse.
- Any change to High/Critical approval routing or to `ReviewPendingApproval`.
- Option C from `eset-local-llm-gateway/threat-assessment.md` (resumable retry on whole-run abort,
  persisting progress so a re-run doesn't reprocess the whole batch) — not pursued; Option B
  supersedes it per the project-owner's 2026-06-25 decision.
