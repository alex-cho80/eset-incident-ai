# Architecture Review: Detection Field Mapping + Sanitizer Coverage Fix

Date: 2026-06-24
Role: claude / architecture_owner

## Scope

Reviewed codex's implementation against `task-spec.md` and all 16 items in
`acceptance-criteria.md`. `git diff --stat`: 6 files changed, 267 insertions(+), 8 deletions(-) —
exactly `detection_notification_builder.py`, `detection_approval_repository.py`, `sanitizer.py`, and
their three test files. No Incident-side file, no `CollectAndNotifyDetections`, no `AnalyzeIncident`,
no prompt, no Settings, no migration touched — matches the spec's Out-of-Scope/Non-goals exactly.
Every changed file was read in full directly (not from codex's self-report).

## 1. Architecture Impact

Compliant. Three new private helper methods (`_detection_user_name`, `_detection_device`,
`_detection_object_name`) are duplicated verbatim across `detection_notification_builder.py` and
`detection_approval_repository.py` rather than factored into a shared module. This mirrors the
codebase's existing convention of intentional vertical-slice duplication between the two files
(`RAW_DETECTION_FIELDS` / `RAW_DETECTION_APPROVAL_FIELDS` were already duplicated this way before
this change) — consistent with the project's established pattern, not a new smell. `Sanitizer`
gained two new compiled regex constants and one new pattern-application line in `sanitize_text`;
no change to its public interface (`pseudonym`, `sanitize_text`, constructor) or callers' usage.
Dependency direction unaffected — all changes are within Infrastructure, no new Domain/Application
coupling.

## 2. Security Impact

Compliant, and this was the highest-risk part of the review. Independently traced
`DOMAIN_ACCOUNT_RE` (`security/sanitizer.py:12-18`) character by character against three adversarial
cases:

- `"nt authority\local service"` → matches (two-word\two-word alternative) → pseudonymized.
  Verified via `test_sanitizer_masks_domain_accounts_consistently`: same input produces the same
  pseudonym across two independent calls (cross-alert correlation preserved without raw exposure).
- `"apache software foundation\tomcat 9.0\bin\tomcat9.exe"` → traced every candidate 2-segment
  sub-span (`foundation\tomcat`, `tomcat 9.0\bin`, `bin\tomcat9.exe`); each is rejected either by the
  `(?<!\\)` lookbehind (a backslash immediately precedes the candidate) or the
  `(?![A-Za-z0-9 ._-]*\\)` lookahead (a backslash is reachable after consuming intervening
  word/space/dot/dash characters) — confirms the atomic-group design correctly excludes every
  interior span of a multi-segment path, not just the obvious ones. Verified via
  `test_sanitizer_preserves_multi_segment_program_paths` with an exact string-equality assertion
  (`result.text == original`), for both the Tomcat path and a `C:\Program Files\...` path.
- `"C:\temp"` (a bare drive-letter path) → the first segment "C:" cannot fully match
  `ACCOUNT_WORD_RE` (`:` is outside the character class), so the word-match terminates at `"C"`
  alone, which is not immediately followed by a literal `\` in the source text (`:` comes next) —
  correctly excluded from matching as an account.

No catastrophic-backtracking risk: `ACCOUNT_TWO_WORD_RE` uses an atomic group (`(?>...)`), and all
quantifiers are bounded by word characters with no nested unbounded repetition — same defensive
posture as requiring "no regex backtracking" for `Severity.parse()` in a prior spec. The new
`WINDOWS_LEGACY_HOME_RE`/`UNIX_HOME_RE` patterns are a direct structural extension of the existing,
already-reviewed `WINDOWS_PATH_RE` (same `<USER_HOME>` replacement convention) — no new replacement
mechanism introduced. `RAW_DETECTION_FIELDS`/`RAW_DETECTION_APPROVAL_FIELDS` are unchanged
(`{"userName", "device"}` in both files, asserted directly in
`test_detection_approval_repository_reads_nested_context_fallbacks`) — the fix does not expand what
bypasses sanitization, only fixes where the already-approved fields' values are sourced from.
`objectName`-via-`context.process.path` correctly stays *off* the allowlist (still routed through
`_safe_text("objectName", ...)`, still sanitized) — verified by reading
`detection_notification_builder.py:58-60` directly, not inferred. All `context`/`process` fallback
lookups are guarded with `isinstance(..., dict)` (lines 99, 106-107, 116-117 in the builder; 168,
175 in the repository) — verified via `test_detection_notification_builder_context_fallbacks_are_guarded`,
which exercises both an empty-string-inside-`context` case and a `context` that is a list, neither
of which raises or leaks an empty value as if it were real data. Independently re-ran `bandit -r
src` (no issues) and `pip-audit` (no known vulnerabilities) directly — both clean.

## 3. Data Impact

Compliant. No schema change, no migration. `PostgresDetectionApprovalRepository._sanitized_payload()`
now additionally populates `userName`/`device` keys (under the same names) when sourced from nested
`context`, and serializes a dict/list `context` as JSON instead of Python repr — both purely
in-memory transformations of the already-existing `payload JSONB` column's contents, no new column,
no new table. Verified via
`test_detection_approval_repository_serializes_context_as_json` that the persisted
`payload["context"]` round-trips through `json.loads` correctly for a Korean-text dict fixture, and
via `test_detection_approval_repository_reads_nested_context_fallbacks` that the email-redaction
behavior for other free-text fields in the same payload is unaffected (`alice@example.com` does not
survive into the payload).

## 4. Operational Impact

Compliant, and directly addresses a real, currently-live gap: all 10 detections presently sitting in
`pending_detection_approvals` (HIGH/CRITICAL, reported in the live manual-trigger run earlier today)
would have rendered with the same dict-repr bug the moment a human clicked approve, completely
independent of the `a38399d` fix already shipped — this fix closes that without requiring any data
migration, since `_sanitized_payload()` is only invoked at `save_pending()` time (new detections
collected after this deploy benefit immediately; the 10 already-pending rows were saved under the
old code and would need a fresh `collect-and-notify` run or manual re-save to pick up the fix
retroactively — flagging this for the deploy-completion conversation, not a blocker for this
review). No new Settings knob, no behavior change to cadence, batching, or the analyzer path (all of
which were the subject of the separate, already-shipped `eset-detection-llm-analysis` fix and remain
untouched here, confirmed via `git diff --stat`).

## 5. Required Tests

All satisfied and independently re-verified directly (not trusting codex's self-report):

- `uv run ruff format --check .` → 169 files already formatted.
- `uv run ruff check .` → All checks passed.
- `uv run mypy src` → Success: no issues found in 122 source files.
- `uv run pytest --cov=src --cov-fail-under=85` → exit code 0 (all tests passing), 87.34% coverage.
- `uv run bandit -r src` → No issues identified.
- `uv run pip-audit` → No known vulnerabilities found.
- Security gate (gitleaks/semgrep/trivy fs/trivy config), re-run directly — see
  `security-gate-report.md`: 0 new findings in any file this fix touched.
- New/updated tests read directly and confirmed to cover every acceptance-criteria item: AC1-AC4 via
  `test_detection_notification_builder_reads_real_firewall_context_fallbacks` and
  `_top_level_values_still_win`; AC6 via `_context_fallbacks_are_guarded`; AC7-AC10 via
  `test_sanitizer_masks_domain_accounts_consistently`,
  `test_sanitizer_preserves_multi_segment_program_paths`,
  `test_sanitizer_masks_legacy_windows_and_unix_home_paths`, and the three pre-existing sanitizer
  tests (unmodified, still passing); AC11-AC13 via the two new
  `test_detection_approval_repository_*` tests.

## 6. Approval or Rejection

**Approved.** Implementation matches `task-spec.md` and all 16 acceptance-criteria items. The
highest-risk element — a new regex intended to catch `DOMAIN\account` strings without colliding with
legitimate multi-segment Windows file paths — was independently traced character-by-character
against three adversarial inputs and holds up; this was verified by direct regex analysis, not just
by trusting the included tests (though the included tests also independently confirm the same
property). No existing Incident file, route, table, or LLM-analysis code path was touched. Diff
stays within the exact file set the spec scoped. Proceeding to ask the project owner for explicit
confirmation before commit/push/deploy, per this project's established human-approval-before-
irreversible-action practice.
