# Task Spec: Detection Field Mapping + Sanitizer Coverage Fix

Owner (specification): claude
Implementer: codex
Status: proposed — awaiting implementation

## Background

After `eset-detection-llm-analysis` (commit `a38399d`) shipped, the project owner reviewed a live
Discord notification for a `DETECTION_CATEGORY_FIREWALL_RULE` detection and reported two problems:

1. The **Device** field shows nothing usable — even where a device identifier exists in the raw
   payload, it is just an opaque UUID, not something an analyst can recognize.
2. The **User** field shows "N/A" even though the Notice footer claims "Detection userName and
   device fields are shown as-is by approved policy" — the approved-raw exposure mechanism is not
   actually firing.

## Root Cause (confirmed by direct code + spec inspection, 2026-06-24)

`SanitizedDetectionNotificationBuilder.build()`
(`infrastructure/discord/detection_notification_builder.py:43,48,53`) reads `userName`, `device`,
and `objectName` only from **top-level** keys on the raw detection dict:
`detection.get("userName")`, `detection.get("device")`, `detection.get("objectName")`.

This matched the sample the original `eset-detections-ingestion` spec was written against ("`userName`
and `device` (hostname) — confirmed present... in the larger [250-record] sample"). It does **not**
match what this tenant's live traffic actually sends for rule/correlation-based categories
(`FIREWALL_RULE`, and the previously-reported `CORRELATION_RULE`/ARP-poisoning case): the union of
top-level keys observed across a live 501-record collect-and-notify run
(`observed_keys` from the manual trigger response) was `category, context, displayName,
networkCommunication, objectHashSha1, objectName, objectTypeName, objectUrl, occurTime, responses,
severityLevel, typeName, uuid` — **no `userName`, no `device`**. For these detection types, ESET
nests the same information one level down, inside `context`, e.g.:

```json
{"userName": "nt authority\\local service",
 "process": {"path": "%PROGRAMFILES%\\apache software foundation\\tomcat 9.0\\bin\\tomcat9.exe"},
 "deviceUuid": "cf48940b-bbc9-41bb-88a7-d4510c5cf214",
 "circumstances": "Security vulnerability exploitation attempt"}
```

Because the builder never looks inside `context`, the User/Device/Object fields fall through to
"N/A" even though the data exists one level down — the "shown as-is by approved policy" Notice text
is currently dead code for this entire class of detection.

A second, independent issue was found while tracing this: ESET does not send a hostname for these
detection types at all, only `deviceUuid` (an opaque UUID). Resolving a UUID to a human-readable
hostname would require a new call to a separate ESET Device/Inventory API, which does not exist in
this project today and is explicitly out of scope for this fix (see Non-goals). This fix makes the
Device field show the UUID instead of "N/A" (strictly better — usable for cross-referencing in the
ESET console — but not a hostname).

A third issue, found independently while reading `_safe_text`'s sanitization path for this report:
`Sanitizer.sanitize_text` (`security/sanitizer.py`) only masks three patterns — email addresses,
`C:\Users\<name>\` paths, and `token/secret/password/webhook=` strings. It has no pattern for
`DOMAIN\username`-style account strings (e.g. `nt authority\local service`) or for file paths
outside the literal `C:\Users\` shape. Because `context` is JSON-dumped as a single free-text blob
and passed through this sanitizer, any personal account name or username embedded inside `context`
that isn't shaped like an email or a `C:\Users\` path passes through unmasked. In the reported
example this happened to be a benign built-in service account, so no real PII leaked — but the same
code path would leak a real human domain account identically. This is a real, if so-far
non-materialized, gap against CLAUDE.md's "Never send raw usernames... or file paths to Discord
without policy approval."

A fourth issue was found while checking whether the same bug exists on the HIGH/CRITICAL
human-approval path (it was not touched by the `a38399d` fix, which only changed
`collect_and_notify_detections.py` and `detection_notification_builder.py`):
`PostgresDetectionApprovalRepository._sanitized_payload()` / `_payload_text()` / `_safe_text()`
(`infrastructure/persistence/detection_approval_repository.py:121-147`) has the **identical**
dict-repr bug (`str(value or fallback)` on a dict `context`, no JSON serialization) and the
**identical** top-level-only key lookup for `userName`/`device` (and additionally silently drops
both keys from the persisted payload entirely if absent at the top level — `_sanitized_payload`
only includes a key `if key in detection`). `ReviewPendingDetectionApproval.approve()`
(`application/use_cases/review_pending_detection_approval.py:50`) later passes this **already
flattened-to-string** `approval.payload` back into
`SanitizedDetectionNotificationBuilder.build()`, which re-sanitizes an already-stringified blob —
harmless but redundant, and the dict-repr text is already baked in by that point. **All 10
detections currently sitting in `pending_detection_approvals` (HIGH/CRITICAL, awaiting human
review) will render with the same dict-repr bug in Discord the moment a human clicks approve**,
completely independent of the `a38399d` fix already shipped.

## Business Requirement

Detection notifications (both the LOW/MEDIUM auto-notify path and the HIGH/CRITICAL
human-approved path) must surface `userName`/device-identifier/process-object information from
wherever ESET actually places it (top level or nested in `context`) so the existing
"shown as-is by approved policy" exposure is not silently dead for entire detection categories. Free
text that is not on the approved-raw allowlist must be defended against personal-account-name
leakage with the same rigor already applied to email addresses, without redacting non-personal
system/software paths that analysts need for root-cause triage.

## Scope

In scope:

1. **Context-fallback field extraction** in `SanitizedDetectionNotificationBuilder.build()`:
   - `userName`: `detection.get("userName")`, falling back to `context.get("userName")` when
     `context` is a dict.
   - `device`: `detection.get("device")`, falling back to `context.get("deviceUuid")` (formatted as
     `f"uuid:{value}"` so an analyst doesn't mistake it for a hostname) then `context.get("device")`.
   - `objectName` (the "Object" field): `detection.get("objectName")`, falling back to
     `context["process"]["path"]` or `context["process"]["name"]` when `context["process"]` is a
     dict. (`objectName` stays **off** `RAW_DETECTION_FIELDS` — unchanged — so a process path
     surfaced this way still goes through the sanitizer like today.)
   - All fallbacks are defensive: only attempt a `context` lookup when `context` is actually a
     `dict`; otherwise behave exactly as today (fall through to the existing fallback/`"N/A"`).
   - The `userName`/`device` raw-bypass policy (`RAW_DETECTION_FIELDS`) is unchanged — these two
     field *labels* are untouched; only where their *value* is sourced from changes.
2. **Identical context-fallback fix** in `PostgresDetectionApprovalRepository._sanitized_payload()`
   so the HIGH/CRITICAL approval path stops silently dropping `userName`/`device` when nested, and
   stores them under the same key names the notification builder already expects.
3. **`context` dict/list JSON-serialization fix** in
   `PostgresDetectionApprovalRepository._payload_text()`/`_safe_text()`, mirroring the fix already
   applied to `SanitizedDetectionNotificationBuilder._safe_text()` in commit `a38399d`
   (`json.dumps(value, ensure_ascii=False)` instead of `str(value)` for dict/list).
4. **New Sanitizer patterns** (`security/sanitizer.py`), additive only, applied in addition to the
   three existing patterns:
   - `DOMAIN_ACCOUNT_RE`: matches a single `word\word`-shaped span (e.g. `NT AUTHORITY\LOCAL
     SERVICE`, `CORP\jdoe`) that is **not** part of a longer backslash-separated path — i.e. not
     immediately preceded or followed by another `\`. This deliberately does **not** match
     multi-segment file paths (`apache software foundation\tomcat 9.0\bin\tomcat9.exe` has a `\`
     on both sides of every interior segment pair, so no sub-span qualifies) and does not match
     drive-letter paths (`C:\temp` — the first segment contains `:`, which the pattern's character
     class excludes). Replace matches via `self.pseudonym("ACCOUNT", original)`, exactly like
     `EMAIL_RE` today, so the same account string maps to the same pseudonym across reports
     (cross-alert correlation without raw exposure). Applied uniformly, with no allowlist for
     "known-safe" built-in accounts — a regex-based allowlist of system account names would be
     fragile and easy to get wrong; consistent pseudonymization is the simpler, more defensible
     control, and analysts can still correlate identical pseudonyms across alerts.
   - Extend the existing user-profile-path coverage (currently `C:\Users\<name>\` only) to also
     cover the legacy `C:\Documents and Settings\<name>\` form and Unix-style `/home/<name>/`,
     replacing with `<USER_HOME>\` / `<USER_HOME>/` respectively — same style as the existing
     `WINDOWS_PATH_RE` replacement, just broader coverage of the same "personal home directory"
     concept.
   - Explicitly **not** in scope: redacting generic system/program paths (`C:\Program Files\...`,
     `C:\Windows\...`, `%PROGRAMFILES%\...`). These do not reveal personal identity and are
     operationally necessary for root-cause analysis (e.g. knowing a detection involves
     `tomcat9.exe` under Tomcat 9.0 is the actionable fact). Blanket-redacting all file paths would
     satisfy CLAUDE.md's literal text but would gut the system's purpose; the already-existing,
     narrower scope (mask only paths that reveal a personal username) is the precedent this fix
     extends, not a new policy stance.

Out of scope (see Non-goals):

- Resolving `deviceUuid` to a hostname via a new ESET Device/Inventory API call.
- Any change to `CollectAndNotifyDetections`, the LLM analyzer wiring, or the Korean-output prompt
  (all shipped and verified in `a38399d`; untouched by this fix).
- Any change to the Incident-side builder/repository/use cases — this fix is Detection-only,
  mirroring how `a38399d` was also Detection-only.
- A general-purpose PII/NER detector. The fix stays within the existing
  regex-pattern-list approach (`Sanitizer.sanitize_text`).

## Trust Boundary

Unchanged: the entire detection payload (including `context` and everything nested inside it)
remains untrusted external input. No detection field is used to construct a query, command, or file
path. The new `DOMAIN_ACCOUNT_RE` pattern is a fixed regex with bounded quantifiers (no
unbounded/nested quantifiers that could backtrack pathologically) — same security property as the
existing patterns.

## Failure Scenarios

- `context` is `None`, a string, or a list instead of a dict (already observed: some detections
  have an empty-string `userName`/`process.path` inside `context`) → every new fallback lookup must
  guard with `isinstance(context, dict)` and otherwise behave exactly as before the fix (no
  exception, fall through to existing fallback chain / `"N/A"`).
- `context["process"]` exists but is not a dict (e.g. `None` or a string) → guarded the same way;
  falls through to `"N/A"` for Object, not a crash.
- A detection has `userName`/`device` at **both** top level and inside `context` with different
  values (not observed, but not ruled out) → top-level wins (existing precedent: top-level is
  checked first, `context` is only a fallback for when top-level is absent/falsy).
- `DOMAIN_ACCOUNT_RE` must not match any span inside a multi-segment file path that the existing
  test suite already exercises (e.g. the Tomcat example, and the existing
  `objectName`/`objectHashSha1`/`objectUrl` test fixtures) — regression-tested explicitly, not just
  inferred.
- The approval-repository fix must not change the **set** of keys included for a detection that
  already has `userName`/`device` at the top level (no behavior change for the case the original
  code already handled correctly) — only the previously-dropped nested case changes.

## Security Requirements

- `RAW_DETECTION_FIELDS` / `RAW_DETECTION_APPROVAL_FIELDS` allowlists are unchanged in content
  (`{"userName", "device"}` only) — this fix does not expand what bypasses sanitization, it fixes
  *where the value comes from* for those two already-approved fields, and fixes JSON-serialization
  + adds new redaction coverage for everything else.
- No new dependency, no new Settings field, no migration.
- `Sanitizer`'s constructor/HMAC-pseudonym mechanism is reused as-is for the new
  `DOMAIN_ACCOUNT_RE` replacement — no new secret material.

## Test Strategy

- Unit tests for `SanitizedDetectionNotificationBuilder` using the exact two real-world payload
  shapes already reported (Tomcat/FIREWALL_RULE context dict, and the earlier ARP-poisoning
  context dict with empty `userName`/`process.path`) asserting: User/Device/Object fields populate
  from `context` when top-level keys are absent; `device` renders as `uuid:<value>` when only
  `deviceUuid` is available; behavior is unchanged (still reads top-level first) when top-level
  keys ARE present (no regression against existing fixture-based tests).
- Unit tests for `Sanitizer.sanitize_text` covering: `DOMAIN_ACCOUNT_RE` masks
  `nt authority\local service` and `CORP\jdoe`-shaped strings consistently (same input → same
  pseudonym, twice); `DOMAIN_ACCOUNT_RE` does **not** mask any span of
  `apache software foundation\tomcat 9.0\bin\tomcat9.exe` or `C:\Program
  Files\...`; `C:\Documents and Settings\<name>\...` and `/home/<name>/...` are masked to
  `<USER_HOME>\.../`/`<USER_HOME>/...` consistent with existing `C:\Users\` behavior; all three
  pre-existing patterns (email, `C:\Users\`, token) still pass unchanged (regression).
- Unit tests for `PostgresDetectionApprovalRepository._sanitized_payload()` (or its persisted
  output, via the existing test harness for this repository) asserting `context`-as-dict renders as
  JSON (not Python repr) and `userName`/`device` populate from nested `context` when absent at top
  level.
- Full existing suite (`ruff format --check`, `ruff check`, `mypy src`,
  `pytest --cov=src --cov-fail-under=85`, `bandit -r src`, `pip-audit`) plus the project's security
  gate (gitleaks/semgrep/trivy fs/trivy config), mirroring the `a38399d` verification precedent.

## Non-goals

- Hostname resolution for `deviceUuid` (separate future task, needs a new ESET API integration).
- Redacting generic system/program file paths.
- Any change to the Incident-side code paths.
- A general PII/NER model — regex-pattern-list approach only, consistent with the existing
  `Sanitizer` design.
