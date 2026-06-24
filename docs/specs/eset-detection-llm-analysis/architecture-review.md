# Architecture Review: LLM Analysis + Korean Output for Detection Notifications

Date: 2026-06-24
Role: claude / architecture_owner

## Scope

Reviewed codex's implementation against `task-spec.md` and all 16 items in
`acceptance-criteria.md`. Diff touches 4 source files and 4 test files only (`git diff --stat`:
8 files changed, 469 insertions(+), 6 deletions(-)) — no migration, no new dependency, no Celery
or Settings change, exactly matching the spec's Out-of-Scope section. Every changed file's full
diff was read directly (`git diff`), not taken from codex's self-report.

## 1. Architecture Impact

Compliant. `CollectAndNotifyDetections` gained one optional constructor parameter
(`analyzer: AnalyzeIncident | None = None`) and two private helpers
(`_analyze_detection`, `_to_analysis_incident`, `_stringify_context`), mirroring
`CollectAndNotifyIncidents`'s existing pattern exactly. No new Protocol, schema, or LLM
infrastructure was introduced — `AnalyzeIncident`, `LlmGateway`, `AnthropicGateway`, and
`config/prompts/incident_analysis.jinja2` are all reused byte-for-byte unmodified (confirmed via
`git status` showing none of those files as changed). The transient `Incident` adapter
(`_to_analysis_incident`) is built from the raw detection dict and discarded after the call — it
is never persisted and does not touch the `Detection` domain entity, consistent with AC4. The
only Protocol change is `DetectionNotificationBuilder.build()` gaining
`analysis: IncidentAnalysisResult | None = None`, identical in shape to
`IncidentNotificationBuilder.build()`. Dependency direction is preserved: the use case
(Application) depends on `AnalyzeIncident` (Application) and `Incident` (Domain); no Infrastructure
import was added to the Domain layer.

## 2. Security Impact

Compliant. Independently inspected `detection_notification_builder.py`: the five new analysis
fields are produced by `_analysis_fields()`, which routes every value through `_safe_text("analysis",
...)` — `"analysis"` is not in `RAW_DETECTION_FIELDS`, so it always passes through
`Sanitizer.sanitize_text`, identical to the Incident builder's equivalent fields. The existing
`RAW_DETECTION_FIELDS = frozenset({"userName", "device"})` allowlist is untouched. The
`_safe_text` dict/list JSON-serialization fix (`json.dumps(raw_value, ensure_ascii=False)`
replacing `str(value or fallback)`) applies uniformly to all fields including `context`, fixing
the originally reported raw-Python-repr leak without weakening sanitization — the JSON string
is still passed into `sanitize_text` afterward for every field except the two raw-allowlisted
ones. Verified via `test_detection_notification_builder_renders_dict_context_as_json` that the
output is valid JSON (not Python repr) and via the existing
`test_detection_notification_builder_preserves_only_approved_raw_fields` (unmodified, still
passing) that PII redaction for non-allowlisted fields is unaffected. The per-detection
analyzer-exception handling in `_analyze_detection()` catches a bare `Exception`, logs via
`logger.warning(..., exc_info=True)`, and returns `None` — no exception detail or raw evidence
is sent anywhere insecure; this matches the spec's deliberate fail-open-without-analysis design
(AC10), independently verified via
`test_collect_detections_analysis_failure_notifies_and_saves_success`, which proves
`save_failure` is never called and the run still reaches `save_success`. No new trust boundary:
detection data flows into `AnthropicGateway` exactly the way incident data already does, reusing
the already-accepted residual-risk decision in `llm-anthropic-gateway/threat-assessment.md`.
Independently re-ran `bandit -r src` (no issues) and `pip-audit` (no known vulnerabilities) — both
clean. Security-gate re-run directly by claude (see `security-gate-report.md`): 0 new findings in
any changed file.

## 3. Data Impact

Compliant. No schema change, no migration. The transient analysis adapter is in-memory only,
never written to a table. `IncidentAnalysisResult` itself is never persisted for Detections any
more than it already is for Incidents (both are notification-time-only artifacts, not stored).
HIGH/CRITICAL detections still route through the unchanged
`PostgresDetectionApprovalRepository.save_pending` path with no analysis attached — confirmed via
`test_collect_detections_never_analyzes_high_or_critical`, which asserts
`analyzer.execute.assert_not_called()` for both HIGH and CRITICAL input. This is intentionally not
a new asymmetry: `ReviewPendingApproval.approve()` for Incidents also never attaches analysis
today, so Detections' approval path stays in parity with Incidents' approval path post-change,
matching the spec's stated business requirement.

## 4. Operational Impact

Compliant, and this was the most important thing to verify for this feature: a single
deterministically-failing analyzer call must not livelock a high-volume Detections run. Traced
`_analyze_detection()` line-by-line: the `try/except Exception` is scoped to the single
`analyzer.execute()` call per detection inside the loop, not the outer `execute()` method — so one
failure logs a warning and returns `None`, the loop continues to the next detection, and the page
still completes normally (cursor persisted, `save_success` reached). This deliberately diverges
from `CollectAndNotifyIncidents`'s current run-aborting behavior on analyzer failure, exactly as
flagged in `task-spec.md`'s Failure Scenarios section — a documented, intentional divergence, not
an oversight. Verified directly via
`test_collect_detections_analysis_failure_notifies_and_saves_success`: of two LOW detections in
one page, the first fails analysis and the second succeeds; both are still notified
(`notified_count == 2`, one with `has_analysis: False` and one with `has_analysis: True`), and
`runs.failure_message is None` / `runs.success_tokens == [None]` confirm the run completed
normally rather than hitting the outer `save_failure` path. No new Settings/throttling knob was
added — `detection_notify_limit` (500/run, unchanged) already bounds the number of new LLM calls
per run, consistent with the spec's Out-of-Scope note.

## 5. Required Tests

All satisfied and independently re-verified (not just trusting codex's self-report):

- `uv run ruff format --check .` -> 169 files already formatted.
- `uv run ruff check .` -> All checks passed.
- `uv run mypy src` -> Success: no issues found in 122 source files.
- `uv run pytest --cov=src --cov-fail-under=85` -> 169 passed, 86.99% coverage.
- `uv run bandit -r src` -> No issues identified.
- `uv run pip-audit` -> No known vulnerabilities found.
- Security-gate (gitleaks/semgrep/trivy fs/trivy config) — see `security-gate-report.md`: 0 new
  findings attributable to this diff; gate FAILs only on the same pre-existing, already-tracked
  Dockerfile/jinja2/urllib findings.
- New/updated tests read directly and confirmed to cover every behavioral acceptance-criteria
  item: `test_collect_detections_attaches_analysis_for_low_and_medium` (AC2, AC4), uses a Korean
  `context` dict and asserts `analyzer.incidents[0].summary` is valid compact JSON with Korean
  text intact; `test_collect_detections_never_analyzes_high_or_critical` (AC3);
  `test_collect_detections_analysis_failure_notifies_and_saves_success` (AC10);
  `test_detection_notification_builder_renders_dict_context_as_json` (AC11);
  `test_detection_notification_builder_footer_without_analysis` and
  `test_detection_notification_builder_attaches_analysis_fields_after_notice` (AC7, AC8, AC9),
  the latter using actual Korean-language `executive_summary`/`action` strings and asserting they
  survive sanitization and rendering unmangled; `test_get_collect_and_notify_detections_wires_analyzer`
  (AC12); `test_detection_approval_use_cases.py`'s `FakeDetectionNotificationBuilder.build()` signature
  update is a mechanical fixture fix-up required by the Protocol change (AC6), not new behavior.

## 6. Approval or Rejection

**Approved.** Implementation matches `task-spec.md` and all 16 items in
`acceptance-criteria.md`. No existing Incident file, route, or table was modified; no new prompt,
schema, or LLM Protocol was introduced; the adapter pattern keeps the diff small and reuses
already-reviewed infrastructure end to end. The one deliberate behavioral divergence from
Incident's current pattern (per-detection analyzer-exception isolation) was flagged in the spec in
advance, is justified by Detections' materially higher volume and per-page cursor persistence, and
is covered by a passing test that proves the run completes instead of livelocking. The
deterministic-verification suite and security gate are both fully green on independent re-run
(security gate FAILs only on the same two pre-existing, unrelated findings already accepted as
technical debt). Proceeding to ask the project owner for explicit confirmation before commit/push
(per `harness.yaml`'s `allow_direct_push: false` and this project's human-approval-before-
irreversible-action practice), then container rebuild and live verification.
