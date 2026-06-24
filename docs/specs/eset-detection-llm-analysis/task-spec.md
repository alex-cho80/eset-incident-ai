# Task Spec: LLM Analysis + Korean Output for Detection Notifications

Date: 2026-06-24
Role: claude / architecture_owner

## Background

A live Detection notification was inspected in Discord and showed two gaps versus the
Incident pipeline: (1) no LLM-generated root-cause/remediation analysis was attached, and
(2) consequently no Korean output, because the Korean instruction lives only in the
analysis prompt template, which Detections never call. The user explicitly chose full
parity with the Incident pipeline (not a cheaper partial fix) after being shown the
volume/cost tradeoff.

## 1. Business Requirement

`CollectAndNotifyDetections`'s auto-notify branch (LOW/MEDIUM severity, post-dedup) must
attach the same `IncidentAnalysisResult` (root cause + remediation, Korean natural-language
values) that `CollectAndNotifyIncidents` attaches today, before sending to Discord.
HIGH/CRITICAL detections keep routing straight to the approval repository with no analysis
attached — this is not a new asymmetry, it mirrors `ReviewPendingApproval.approve()`, which
also never attaches analysis to an approved Incident's notification today.

Static field labels (Category/Occurred/User/Device/Object/SHA1/Notice) stay in English,
unchanged. Only the new LLM-generated analysis values are Korean — this matches the
existing Incident builder exactly (`incident_analysis.jinja2` rule 9 translates natural-
language *values*, never JSON field names or the `priority` enum), and matches what the
user actually asked for ("분석 결과"/analysis result in Korean, not the whole message).

## 2. Data Flow

```
CollectAndNotifyDetections._execute()  [LOW/MEDIUM branch only]
  -> _to_analysis_incident(detection, severity) -> Incident   (new, transient adapter;
       title = displayName or uuid; summary = context (JSON-dumped if dict/list, else str);
       NOT the Detection domain entity, not persisted — exists only to satisfy
       LlmGateway.analyze(incident: Incident, ...)'s existing typed contract, the same way
       CollectAndNotifyIncidents._to_domain_incident() already adapts a raw incident dict)
  -> AnalyzeIncident.execute(incident=..., tenant_scope="default")   [UNCHANGED — same
       PgVectorRepository RAG search, same AnthropicGateway, same incident_analysis.jinja2,
       same IncidentAnalysisResult schema; zero new LLM infra]
  -> SanitizedDetectionNotificationBuilder.build(detection, analysis)   [analysis: 
       IncidentAnalysisResult | None = None, new optional param — mirrors
       SanitizedIncidentNotificationBuilder.build() exactly]
  -> Notifier.send(...)
```

No new prompt template, no new Pydantic schema, no change to `LlmGateway` Protocol, no
change to `AnthropicGateway`. The adapter is the only new "LLM-facing" code.

## 3. Trust Boundary

Unchanged from the already-reviewed Incident analysis boundary
(`llm-anthropic-gateway/threat-assessment.md`): ESET fields and RAG evidence are untrusted
input to the LLM; the prompt's rules 1-2 already say to ignore embedded instructions; LLM
output is advisory only and cannot execute remediation directly
(`IncidentAnalysisResult.requires_destructive_approval` already gates that, unchanged). No
new trust boundary is introduced by reusing this path for Detections.

## 4. Failure Scenarios

- **Anthropic API failure mid-run (new behavior, diverges from today's Incident behavior on
  purpose):** today, `CollectAndNotifyIncidents` lets an analyzer exception propagate
  uncaught, aborting the whole run via `execute()`'s outer try/except. For Detections this
  is materially riskier: volume is ~2-3 orders of magnitude higher than Incidents, and the
  cursor is only persisted after a page fully completes — a single deterministically-failing
  record (e.g., one that twice fails structured-output validation) would re-fetch and
  re-fail the same page forever, livelocking the whole pipeline. Decision: catch the
  analyzer's exception per-detection inside the loop, log it, and send the notification
  without analysis attached (same shape as `analysis=None` today) rather than aborting the
  run. The detection still counts toward `notified_count`; nothing is silently dropped.
- **RAG evidence is a poor match for a routine detection** (e.g., vector search on a
  Detection's title returns Incident-shaped evidence that doesn't really apply): degrades
  gracefully today via the prompt's existing `no-supporting-evidence` sentinel and
  `false_positive_probability`/`unknowns` fields — no new handling needed.
- **`context` is a dict/list, not a string** (observed live: produced a raw Python-repr
  blob in the Discord description and would otherwise also leak into the LLM prompt as
  Python repr instead of valid JSON): JSON-serialize (`json.dumps(..., ensure_ascii=False)`)
  before sanitizing/embedding, instead of relying on `str()`.

## 5. Security Requirements

- No raw PII bypass beyond what's already approved: `RAW_DETECTION_FIELDS`/
  `RAW_DETECTION_APPROVAL_FIELDS` are unchanged. The new analysis fields go through the
  exact same `_safe_text`-equivalent sanitization the Incident builder already uses for its
  `_analysis_fields()` (`self._sanitizer.sanitize_text(...)`).
- `Sanitizer`, `PromptInjectionFilter`, and the evidence-id allowlist check in
  `AnthropicGateway._parse_and_validate()` are reused unmodified.
- No new secret, credential, or external endpoint is introduced.

## 6. Test Strategy

- Unit tests for `CollectAndNotifyDetections`: LOW/MEDIUM calls the analyzer and passes its
  result into `notification_builder.build()`; HIGH/CRITICAL never calls the analyzer
  (`assert_not_called`); analyzer exception -> notification still sent with `analysis=None`,
  run still reaches `save_success` (not aborted).
- Unit test for `SanitizedDetectionNotificationBuilder`: with `analysis=None` footer reads
  "AI analysis is not yet attached..."; with an `IncidentAnalysisResult` provided, the new
  fields appear and footer changes, while the existing raw-fields Notice field is untouched.
- Unit test for the dict/list `context` JSON-serialization fix.
- Full deterministic-verification suite (`ruff format --check`, `ruff check`, `mypy src`,
  `pytest --cov=src --cov-fail-under=85`, `bandit -r src`, `pip-audit`) green.
- Security-gate (gitleaks/semgrep/trivy fs/trivy config): no new findings beyond the
  already-documented pre-existing ones.

## Out of Scope

- No change to HIGH/CRITICAL's approval-time notification (matches existing Incident
  asymmetry).
- No new Settings/throttling knob for LLM call volume — `detection_notify_limit` (already
  500/run) already bounds LLM calls per run; if real cost/latency after deployment warrants
  tuning, that is a config change, not a new feature.
- No change to `detection_client.py`, migrations, Celery wiring, or API routes.
