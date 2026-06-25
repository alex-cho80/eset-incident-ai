# Architecture Review: Remove human-approval gate for HIGH/CRITICAL

## Architecture impact
Dependency direction unchanged — no new imports added to `collect_and_notify_incidents.py` /
`collect_and_notify_detections.py` (verified via diff: pure deletion of a branch, zero new
`import`/`from` lines). Domain layer (`domain/`) untouched; confirmed no
fastapi/sqlalchemy/langgraph/anthropic/openai/discord references in `src/eset_incident_ai/domain/`.
`scripts/backfill_pending_detection_approvals.py` sits outside the hexagonal layering (same
position as `api/dependencies.py` composition root) and is allowed to import infrastructure
directly — consistent with existing convention.

## Security impact
This is the intended effect of the change, not a side effect: HIGH/CRITICAL no longer requires
human approval before notification. CLAUDE.md updated in the same diff so the written policy
matches actual behavior (acceptance criteria #3). No change to sanitization rules, PII handling,
or what data reaches Discord/Ollama — only the severity-based *routing* changed. Backfill script
never logs secret values (verified: only env-var *names* appear in error messages, e.g.
`"DISCORD_WEBHOOK_URL is empty"`).

## Data impact
No schema change. `pending_approvals`/`pending_detection_approvals` tables and their read/review
API endpoints are left in place (explicitly out of scope) — they become a manual-review-only
escape hatch with nothing new feeding them going forward (Incident side: 0 rows already; Detection
side: 50 rows drained by the one-time backfill, not by this code path).

## Operational impact
Behavior change is live the moment this is deployed — every future HIGH/CRITICAL incident/detection
auto-notifies immediately. Backfill of the 50 existing pending detections is a separate, manual,
~2-2.5 hour run (Ollama `num_parallel=1`, ~150-180s/call) — must be triggered explicitly after
deploy, not automatically.

## Required tests
Existing test suite updated and passing (183 passed, 87.28% coverage, mypy/ruff/bandit clean,
pip-audit blocked by sandbox DNS — known pre-existing environment limitation, not introduced by
this change). New coverage: `test_collect_and_notify_routes_critical_severity_to_notification`,
backfill mapping function test.

## Approval or rejection
**Approved.** Diff is a minimal, surgical deletion matching the spec exactly; no architecture
violation introduced; policy doc kept in sync with code.
