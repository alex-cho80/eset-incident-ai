# Acceptance Criteria: LLM Analysis + Korean Output for Detection Notifications

1. `CollectAndNotifyDetections` accepts an optional `analyzer: AnalyzeIncident | None`
   constructor parameter, mirroring `CollectAndNotifyIncidents`.
2. For the LOW/MEDIUM (auto-notify) branch, when `analyzer` is set, it is called with a
   transient `Incident`-shaped adapter built from the raw detection dict before
   `notification_builder.build()` is invoked.
3. For the HIGH/CRITICAL branch (approval-pending), the analyzer is never called — verified
   by a test asserting `analyzer.execute` is not awaited/called for HIGH/CRITICAL input.
4. The adapter (`_to_analysis_incident` or equivalently named) sets `title` from
   `displayName` (fallback `uuid`), `summary` from `context` (JSON-dumped via
   `json.dumps(..., ensure_ascii=False)` if the raw value is a `dict`/`list`, else `str()`),
   and `severity` from the already-computed `Severity`. No existing `Detection`
   domain entity construction is introduced or changed.
5. No new prompt template, no change to `IncidentAnalysisResult`, no change to the
   `LlmGateway` Protocol signature, no change to `AnthropicGateway`.
6. `application/ports/detection_notification_builder.py`'s `DetectionNotificationBuilder`
   Protocol's `build()` gains `analysis: IncidentAnalysisResult | None = None`, matching
   `IncidentNotificationBuilder`'s existing shape.
7. `SanitizedDetectionNotificationBuilder.build()` accepts the new `analysis` parameter;
   when provided, appends the same five analysis fields (Analysis Summary, Confidence,
   Evidence Coverage, Evidence, Immediate Action) that
   `SanitizedIncidentNotificationBuilder._analysis_fields()` produces, sanitized the same
   way; footer text switches between "AI analysis is not yet attached. Collector
   notification only." and "Local RAG analysis attached. Review before action." exactly
   like the Incident builder's two footer strings.
8. The existing raw-fields `Notice` field (about `userName`/`device` being shown as-is) is
   unchanged in content and position when analysis is attached.
9. Static field labels (Category/Occurred/User/Device/Object/Object URL/SHA1/Notice) remain
   in English in both the `analysis=None` and `analysis=<result>` cases.
10. A raised exception from `analyzer.execute(...)` for a single detection is caught inside
    `CollectAndNotifyDetections`'s loop, logged, and that detection's notification is still
    sent with `analysis=None` (not skipped, not aborting the run). `notified_count` still
    increments for it. The collection run still reaches `save_success` afterward (verified
    by a test that makes the analyzer raise on one call among several and asserts the run
    completes with the expected counts).
11. `context` (or any field routed through the same stringify path) that is a `dict`/`list`
    renders as compact JSON (`json.dumps(..., ensure_ascii=False)`) in both the Discord
    `description` and the analysis prompt's `summary` input — not Python's `str(dict)` repr.
    Existing string-valued `context` behavior is unchanged.
12. `get_collect_and_notify_detections()` in `api/dependencies.py` wires
    `analyzer=AnalyzeIncident(vector_repository=PgVectorRepository(settings.database_url),
    llm_gateway=_get_llm_gateway(settings))`, matching
    `get_collect_and_notify_incidents()`'s wiring exactly.
13. No change to `detection_client.py`, `detection_approval_repository.py`
    (`RAW_DETECTION_APPROVAL_FIELDS` unchanged), `migrations/`, Celery wiring/Settings
    defaults, or any `/detections/*` API route.
14. `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy src`,
    `uv run pytest --cov=src --cov-fail-under=85`, `uv run bandit -r src`,
    `uv run pip-audit` all pass.
15. Security-gate (`gitleaks detect --no-banner`, `semgrep scan --config auto`,
    `trivy fs .`, `trivy config .`) reports no new finding beyond the already-documented
    pre-existing ones (Dockerfile `HEALTHCHECK`, `smoke_check.py` urllib,
    `anthropic_gateway.py` jinja2).
16. New/updated unit tests exist for items 2, 3, 7, 9, 10, 11 above and all pass.
