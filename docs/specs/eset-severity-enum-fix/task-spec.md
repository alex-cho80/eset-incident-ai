# Task Spec: Fix ESET severity-enum parsing (human-approval gate bypass)

## Business Requirement

`CollectAndNotifyIncidents` must correctly recognize HIGH/CRITICAL severity on real ESET
incidents so the human-approval gate (CLAUDE.md: "High and critical incidents require human
approval before notification or remediation") actually fires. It currently never fires for any
real incident.

## Root Cause (confirmed 2026-06-24 via live API call against `eu.incident-management.eset.systems`)

ESET Connect's `/v2/incidents` returns `severity` as the full proto-style constant, e.g.
`INCIDENT_SEVERITY_LEVEL_LOW`, `INCIDENT_SEVERITY_LEVEL_MEDIUM`, `INCIDENT_SEVERITY_LEVEL_HIGH`,
`INCIDENT_SEVERITY_LEVEL_UNSPECIFIED` (per
`https://help.eset.com/eset_connect/en-US/incident_management_v2_incidents_get.html` and verified
against 20 live incidents — no `CRITICAL` level exists on ESET's side).

`SanitizedIncidentNotificationBuilder.severity()`
(`src/eset_incident_ai/infrastructure/discord/incident_notification_builder.py`) does:

```python
text = str(incident.get("severity") or "low").lower()
if text in {severity.value for severity in Severity}:  # {"low","medium","high","critical"}
    return Severity(text)
return Severity.LOW
```

`"INCIDENT_SEVERITY_LEVEL_HIGH".lower()` does not match any `Severity` value, so every real
incident silently falls through to `Severity.LOW`. This is the only call site that feeds
`CollectAndNotifyIncidents`'s `if severity in {Severity.HIGH, Severity.CRITICAL}` branch
(`src/eset_incident_ai/application/use_cases/collect_and_notify_incidents.py:78`), so that branch
has never executed against real ESET data.

A second, structurally identical bug exists in `NormalizeIncident.execute()`
(`src/eset_incident_ai/application/use_cases/normalize_incident.py:17`) — there it would raise
`ValueError` instead of silently defaulting, but this class is currently unused dead code (no
caller anywhere in `src/`), so it has no live blast radius today. Fix it anyway so it doesn't
become a live bug the next time someone wires it up.

## Data Flow

No change to data flow. Same untrusted ESET JSON, same point of entry
(`EsetIncidentClient.iter_incidents`/`get_incident`) — only the severity-string interpretation
changes.

## Trust Boundary

Unchanged: ESET payload is still untrusted input. The fix must not introduce a new way for
attacker-controlled incident text to influence control flow beyond exact-string matching against a
fixed allowlist of known ESET enum values.

## Failure Scenarios

- Unknown/missing/garbage severity string (including anything attacker-supplied in a field that
  happens to be reused as `severity`) → must default to `Severity.LOW`, same as today. Do not
  raise, do not crash the collection run.
- `INCIDENT_SEVERITY_LEVEL_UNSPECIFIED` → `Severity.LOW` (preserves existing "unknown severity ⇒
  treat as low, don't block" behavior — this is not a new policy decision, just preserving status
  quo for the "no information" case).
- Mixed case / extra whitespace in the raw value → must still parse correctly (defensive, ESET is
  external and not contractually guaranteed to be byte-exact).

## Acceptance Criteria

1. `severity()` (or an equivalent parsing function used by it) maps `INCIDENT_SEVERITY_LEVEL_LOW`
   → `Severity.LOW`, `INCIDENT_SEVERITY_LEVEL_MEDIUM` → `Severity.MEDIUM`,
   `INCIDENT_SEVERITY_LEVEL_HIGH` → `Severity.HIGH`, `INCIDENT_SEVERITY_LEVEL_UNSPECIFIED` →
   `Severity.LOW`.
2. The existing short-form inputs (`"low"`, `"medium"`, `"high"`, `"critical"`, `"info"`,
   `"informational"`) continue to parse exactly as before — no regression for any existing caller
   or test fixture that still uses the short form.
3. Unknown/garbage/missing input still defaults to `Severity.LOW` and never raises.
4. `CollectAndNotifyIncidents`, given a fixture incident with
   `{"severity": "INCIDENT_SEVERITY_LEVEL_HIGH"}`, routes it to `approval_repository.save_pending`
   (not to `notifier.send`) — i.e. an end-to-end test proving the gate now actually fires for the
   real ESET format.
5. `NormalizeIncident.execute()` parses the same ESET format without raising (fix the latent bug
   even though currently unused).
6. `Severity` continues to have exactly 4 members (`low`, `medium`, `high`, `critical`) — do not
   remove `critical` even though ESET itself never sends it; it stays available for any future
   internal escalation logic.
7. No change to `Severity` enum's own values/serialization (Discord embed title, DB storage, etc.
   must not change format).

## Security Requirements

- Parsing must be a pure string-matching function (fixed allowlist lookup), no regex backtracking
  risk, no `eval`/dynamic dispatch.
- Must not log the raw incident text in a way that bypasses `Sanitizer` (this fix doesn't add any
  new field to Discord/LLM output, so no new sanitization surface).
- Must not change which fields are treated as trusted vs untrusted.

## Test Strategy

- Unit tests on the parsing function/`severity()` covering: all 4 real ESET enum forms (including
  `UNSPECIFIED`), all existing short forms, mixed case, unknown string, missing key, empty string.
- Unit test on `NormalizeIncident.execute()` with a real-format payload, asserting no exception and
  correct `Severity`.
- Integration-style test on `CollectAndNotifyIncidents._execute()` (already has a fake
  `IncidentSource`/`ApprovalRepository` pattern in `tests/unit/test_collect_and_notify_incidents.py`)
  proving a `INCIDENT_SEVERITY_LEVEL_HIGH` fixture incident lands in `pending_approval_count`, not
  `notified_count`.
- Full existing deterministic-verification suite must still pass
  (`ruff`, `mypy`, `pytest --cov=src --cov-fail-under=85`, `bandit`, `pip-audit`).

## Out of Scope

- Calling ESET's Detections API or adding threat-category/type classification (separate, larger
  task — see [[project-eset-incident-ai]] memory note on unused `Detection.category`).
- Changing `status`/`resolveReason` parsing — neither currently feeds any branching logic, so the
  same format mismatch there has no behavioral impact today.
- Re-evaluating already-delivered notifications retroactively (no backfill/reprocessing of past
  incidents).
