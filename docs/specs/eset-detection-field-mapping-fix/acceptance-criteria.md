# Acceptance Criteria: Detection Field Mapping + Sanitizer Coverage Fix

1. `SanitizedDetectionNotificationBuilder.build()`'s **User** field renders `context["userName"]`
   when `detection.get("userName")` is absent/falsy and `context` is a dict; unchanged ("N/A") when
   neither is present.
2. `SanitizedDetectionNotificationBuilder.build()`'s **Device** field renders
   `f"uuid:{context['deviceUuid']}"` when `detection.get("device")` is absent/falsy,
   `context` is a dict, and `context.get("deviceUuid")` is truthy; falls back further to
   `context.get("device")` if `deviceUuid` is absent; unchanged ("N/A") when none are present.
3. `SanitizedDetectionNotificationBuilder.build()`'s **Object** field renders
   `context["process"]["path"]` (or `["name"]` if `path` absent) when `detection.get("objectName")`
   is absent/falsy and `context["process"]` is a dict; unchanged ("N/A") when none are present.
4. When `detection.get("userName")` / `detection.get("device")` / `detection.get("objectName")` ARE
   present at the top level, behavior is byte-for-byte unchanged from before this fix (top-level
   always wins; existing passing tests for this case must still pass without modification).
5. `userName`/`device` values sourced via the new `context` fallback still bypass the sanitizer
   exactly like top-level-sourced values do today (still routed through `_safe_text("userName", ...)`
   / `_safe_text("device", ...)`, still in `RAW_DETECTION_FIELDS`); `objectName`-sourced values via
   the new `context["process"]` fallback still go through the sanitizer (objectName stays off the
   allowlist).
6. All `context`/`process` fallback lookups are guarded by `isinstance(..., dict)` and never raise
   for `context` being `None`, a string, a list, or `context["process"]` being non-dict — proven by
   a test using the previously-reported real payload where `context["userName"]` and
   `context["process"]["path"]` are present-but-empty strings (must still fall through correctly,
   not crash, not render an empty string as if it were data).
7. `Sanitizer.sanitize_text` gains a `DOMAIN_ACCOUNT_RE`-equivalent pattern that masks
   `nt authority\local service` and `CORP\jdoe`-shaped single-segment account strings via
   `self.pseudonym("ACCOUNT", original)`, with the same input producing the same pseudonym across
   two separate calls (proven by a test asserting equality of two independent
   `sanitize_text()` calls on the same input string).
8. The same pattern from AC7 does **not** alter any character of
   `apache software foundation\tomcat 9.0\bin\tomcat9.exe` or `C:\Program Files\Vendor\App\app.exe`
   when run through `sanitize_text` — proven by an explicit equality assertion
   (`result.text == original`) for both example strings.
9. `Sanitizer.sanitize_text` masks `C:\Documents and Settings\<name>\...` and `/home/<name>/...` to
   `<USER_HOME>\...`/`<USER_HOME>/...` respectively, consistent with existing `C:\Users\<name>\...`
   behavior (which must remain unchanged — regression-tested).
10. All three pre-existing `Sanitizer` patterns (email, `C:\Users\`, token/secret/password/webhook)
    continue to pass their existing tests unmodified — zero regressions.
11. `PostgresDetectionApprovalRepository._sanitized_payload()` includes `userName`/`device` in the
    persisted payload (under those same key names) when sourced from a nested `context` dict, even
    though the top-level detection dict does not have those keys (today it silently omits them via
    `if key in detection`).
12. `PostgresDetectionApprovalRepository`'s payload serialization renders a dict/list `context`
    value as JSON (`json.dumps(..., ensure_ascii=False)`), not Python `str()` repr — mirroring the
    `a38399d` fix already applied to `SanitizedDetectionNotificationBuilder._safe_text`. Proven by a
    test asserting the persisted `payload["context"]` is valid JSON for a Korean-text dict context
    fixture.
13. No change to `RAW_DETECTION_FIELDS` or `RAW_DETECTION_APPROVAL_FIELDS` contents (still exactly
    `{"userName", "device"}` in both files) — proven by an explicit equality assertion in a test.
14. No change to `CollectAndNotifyDetections`, `AnalyzeIncident`, `AnthropicGateway`, any prompt
    file, any Settings field, or any Incident-side file — proven by `git diff --stat` touching only
    `detection_notification_builder.py`, `detection_approval_repository.py`, `sanitizer.py`, and
    their corresponding test files (plus this spec's own two files).
15. `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`,
    `uv run pytest --cov=src --cov-fail-under=85`, `uv run bandit -r src`, `uv run pip-audit` all
    pass with zero new findings attributable to this change.
16. Security gate (gitleaks, semgrep, trivy fs, trivy config) re-run directly against the working
    tree shows zero new findings attributable to any file changed by this fix.
