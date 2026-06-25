# Architecture Review: Incident Analyzer-Exception Resilience

Date: 2026-06-25
Role: claude / architecture_owner

## Scope

Reviewed codex's implementation against all 6 acceptance criteria in `task-spec.md`. Diff
(`git diff --stat`): 1 source file (+17/-4 lines), 1 test file (+148/-35 lines including 2 new
tests). No new dependency, no new file, no migration. Full diff read directly by claude, not taken
from codex's self-report. Independently re-ran the full verification gate (`ruff check`, `mypy
src`, `pytest --cov`, `bandit -r src`, `pip-audit`) — all results matched
`implementation-report.md`'s figures exactly (87.33% coverage, 122 mypy-clean files).

## 1. Architecture Impact

Compliant. The only new import is `logging` (stdlib). `collect_and_notify_incidents.py:96-109`
wraps exactly the `self._analyzer.execute(...)` call in `try`/`except Exception`, reproducing
`collect_and_notify_detections.py`'s `_analyze_detection()` pattern verbatim in message shape, log
field name choice (`incident_id` mirrors `detection_id`), and `exc_info=True` usage. No new
abstraction, no new Protocol, no change to `AnalyzeIncident` or `LlmGateway`. `analysis = None` is
still initialized before the `if self._analyzer is not None:` guard (line 94, unchanged), so the
new `try`/`except` only ever narrows what happens *inside* that existing guard — confirmed by
reading the surrounding 30 lines directly, not just the diff hunk.

## 2. Security Impact

Compliant, no new risk. The `except` block reads only `incident.get("uuid")` /
`incident.get("displayName")` for the log message — identical fallback chain to
`_analyze_detection`'s existing `detection_id` construction, already accepted in a prior security
review for the equivalent Detection code path. No `incident.title`/`incident.summary` (the
sanitizer-protected fields) are read anywhere in the new code. The `except Exception` clause is
scoped to the three lines of the analyzer call only — confirmed by inspection that
`self._notifier.send(...)`, `self._notification_repository.mark_delivered(...)`, and everything
else in the loop remain outside the `try` block and still propagate normally. Ran the
`security-gate` skill checklist directly:
- Secrets: none introduced. PASS.
- Personal data leakage: log identifier matches the already-accepted Detection pattern; no
  sanitizer-protected field is logged. PASS.
- Unsafe automation: none — the change only logs and continues. PASS.
- Missing approval gates: High/Critical routing (`collect_and_notify_incidents.py:77-86`) is
  outside this diff entirely (`git diff --stat` shows changes start at line 93) — confirmed
  untouched. PASS.
- Prompt injection handling: not applicable, no prompt construction in this file. N/A.

`gitleaks`/`semgrep`/`trivy` remain unavailable in this environment (pre-existing gap, not new to
this task — see `eset-local-llm-gateway/security-gate-report.md` for the same finding one task
ago). Independently re-ran `bandit -r src` (0 issues) and `pip-audit` (no known vulnerabilities) —
both clean.

## 3. Data Impact

No change. No schema, no migration, no new persisted field. `IncidentCollectionResult`'s shape is
unchanged; only whether `save_failure()` is reached for an analyzer-only failure changes (it is no
longer reached for that case, per spec).

## 4. Operational Impact

This is the intended operational change: an Ollama analysis failure (timeout, connection error,
exhausted validation retries) on a Low/Medium incident no longer aborts the rest of that
collection run or marks it as a failed run. Independently verified the regression guard
(`test_collect_and_notify_source_iterator_failure_still_records_failure`) actually exercises a
non-analyzer failure path (a `FailingIncidentSource` raising mid-iteration) and asserts
`save_failure` is still called with the original exception's message — this is the test that
proves the fix didn't overreach into the rest of `_execute()`'s fail-closed behavior. Read it
directly: it does construct a real `CollectAndNotifyIncidents` with a failing source and asserts
`pytest.raises(TimeoutError)` plus `runs.failure_message` — matches AC4 exactly, not a weaker
proxy for it.

## 5. Required Tests

`test_collect_and_notify_incidents.py` gained two tests, both read directly:
- An analyzer-failure-degrades-gracefully test: first of two Low/Medium incidents fails analysis,
  asserts both still get notified, the failing one's log record carries `incident_id` and
  `exc_info`, and the log message does not contain the (deliberately PII-shaped) title/summary
  fixture text used in the test — directly testing AC6, not just asserting no exception.
- The AC4 regression guard described above.

Both new tests follow the file's existing fake-repository/fake-source conventions (no new test
infrastructure introduced).

## 6. Approval

**Approved.** The implementation matches `task-spec.md` precisely: narrowly scoped exception
handling, faithful reuse of the already-reviewed Detection pattern, and an explicit regression test
proving the rest of the fail-closed behavior is untouched. This resolves the "Decision required"
item in `docs/specs/eset-local-llm-gateway/threat-assessment.md` as Option B. No outstanding
concern before merge.
