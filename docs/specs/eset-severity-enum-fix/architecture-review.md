# Architecture Review: ESET Severity Enum Fix

Date: 2026-06-24
Role: claude / architecture_owner

## Scope

Reviewed codex's implementation against `task-spec.md`'s 7 acceptance criteria. Diff touches:

- `src/eset_incident_ai/domain/enums/severity.py` (+12)
- `src/eset_incident_ai/application/use_cases/normalize_incident.py` (1 line changed)
- `src/eset_incident_ai/infrastructure/discord/incident_notification_builder.py` (-6/+1)
- `tests/unit/test_collect_and_notify_incidents.py` (+69)
- `tests/unit/test_normalize_incident.py` (new, +20)

## 1. Architecture Impact

Compliant. `Severity.parse()` is added as a classmethod on the Domain-layer enum itself
(`severity.py`), so both Application (`normalize_incident.py`) and Infrastructure
(`incident_notification_builder.py`) call inward/sideways into Domain rather than duplicating
parsing logic or introducing a new cross-layer module. Dependency direction
(API/Infrastructure -> Application -> Domain) is preserved; no new imports of FastAPI/SQLAlchemy/
LangGraph/Anthropic SDK/OpenAI SDK/Discord SDK were added to the Domain layer. Diff is minimal —
no unrelated refactoring.

## 2. Security Impact

Compliant. `Severity.parse()` is a pure string-matching function: `.strip().lower()`, a fixed
`"incident_severity_level_"` prefix strip, then exact-match against a small fixed allowlist
(`{"informational","info","unspecified"}` and the enum's own `.value` set). No regex, no `eval`,
no dynamic dispatch — satisfies the spec's "Security Requirements" section directly. Unknown/
garbage/empty/`None` input falls through to `Severity.LOW` and never raises, preserving the
existing fail-safe default (AC3). This closes the actual security gap motivating the fix: HIGH/
CRITICAL incidents in real ESET format now correctly route to the human-approval gate in
`CollectAndNotifyIncidents` instead of silently defaulting to LOW and bypassing
`approval_repository.save_pending` (AC4, proven by
`test_collect_and_notify_routes_real_eset_high_severity_to_pending_approval`). Independently
re-ran `bandit -r src` (no issues) and `pip-audit` (no known vulnerabilities) — both clean.

## 3. Data Impact

Compliant. No change to `Severity`'s own enum values or serialization — `len(Severity) == 4`,
members unchanged (`low/medium/high/critical`), so Discord embed text and any DB-stored severity
string are unaffected (AC6, AC7). No new field is read from or sent to Discord/LLM; the trust
boundary (ESET payload = untrusted input) is unchanged — `severity` is still read from the same
untrusted dict and only the string-matching logic changed, satisfying the spec's "Trust Boundary"
section.

## 4. Operational Impact

Fixes a live production bug with no migration or deploy-order dependency — pure code change,
backward compatible with existing short-form fixtures/tests (AC2, confirmed via parametrized test
covering 14 cases including legacy short forms). `NormalizeIncident.execute()`'s latent
`ValueError`-raising bug is also fixed (AC5) even though that class has no live caller today,
preventing it from becoming a live crash the next time it's wired up. Requires a container rebuild
to take effect in the running worker (next step, not yet done).

## 5. Required Tests

All satisfied and independently re-verified (not just trusting codex's self-report):

- `uv run ruff check .` → All checks passed.
- `uv run mypy src` → Success: no issues found in 109 source files.
- `uv run pytest --cov=src --cov-fail-under=85` → 117 passed, 88.13% coverage.
- `uv run bandit -r src` → No issues identified.
- `uv run pip-audit` → No known vulnerabilities found.
- Security-gate (gitleaks/semgrep/trivy) — see `security-gate-report.md`: 0 new findings from this
  diff; gate FAILs only on pre-existing, already-tracked Dockerfile/jinja2/urllib findings unrelated
  to this change.
- Diff-level test coverage: all 7 acceptance criteria have a corresponding assertion in
  `test_collect_and_notify_incidents.py` (parametrized severity-parsing cases + end-to-end approval
  routing) and `test_normalize_incident.py` (latent-bug fix).

## 6. Approval or Rejection

**Approved.** Implementation matches `task-spec.md` exactly, stays within scope (no
status/resolveReason/Detections-API changes, as explicitly out of scope), and the deterministic-
verification suite is fully green on independent re-run. Security-gate findings are pre-existing
technical debt unrelated to this diff and do not block this fix. Proceeding to commit, push, and
container rebuild + live verification.
