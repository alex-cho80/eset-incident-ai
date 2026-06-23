# Task Spec: Anthropic LLM Gateway for Incident Analysis

Owner (specification): claude
Implementer: codex
Status: proposed — awaiting implementation

## Business Requirement

PROJECT_STATUS.md lists "Replace `LocalAnalysisGateway` with OpenAI or Anthropic gateway when
provider credentials are ready" as a remaining enhancement. The live analysis path
(`AnalyzeIncident` -> `LlmGateway.analyze()`) is currently wired to `LocalAnalysisGateway`, a
deterministic stub: fixed f-string summaries, arithmetic confidence, no model call
(`infrastructure/llm/local_gateway.py`). The business need is real, evidence-grounded root-cause
and remediation analysis from an actual LLM.

## Scope

In scope:

- Implement `AnthropicGateway.analyze()`
  (`src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py`) as a real implementation of the
  `LlmGateway` / `AnalysisGateway` protocol, calling the Anthropic Messages API once per incident
  and returning a validated `IncidentAnalysisResult`.
- A provider factory in `api/dependencies.py` keyed on `settings.llm_provider`: `"anthropic"` with
  a configured API key resolves to `AnthropicGateway`; anything else (including a configured
  provider with a missing key) resolves to `LocalAnalysisGateway`. The choice is made once at
  startup/wiring time, not per request.
- New `Settings` fields (`settings/config.py`), environment-sourced only:
  - `anthropic_api_key: str = ""`
  - `anthropic_model: str = ""` (empty means "not configured"; confirm the current Anthropic
    model id with the project owner before picking a hardcoded default — do not guess one)
  - `llm_timeout_seconds: float = 30.0`
  - `llm_max_retries: int = 2`
- `anthropic` Python SDK added to `pyproject.toml` dependencies.
- New prompt template `config/prompts/incident_analysis.jinja2`: carries the same security framing
  already proven in `root_cause_analyst.jinja2` (untrusted data, ignore embedded instructions,
  evidence-ID-grounded claims, JSON-only), extended to request the **full**
  `IncidentAnalysisResult` schema (root cause and remediation) in a single call.
  `root_cause_analyst.jinja2` / `remediation_planner.jinja2` are reserved for the future
  multi-node LangGraph pipeline (ADR-002) and must not be modified by this task.
- `Sanitizer.sanitize_text()` applied to `incident.title` and `incident.summary` before they are
  interpolated into the prompt — this is the same untrusted-ESET-data path that already reached
  Discord unsanitized; it must not reach a third-party LLM API unsanitized either
  (`docs/architecture/trust-boundaries.md`: "LLM receives sanitized incident data ... only").
- `PromptInjectionFilter` applied to the same fields. If triggered: do not block the incident, do
  not silently strip text; append a fixed note to `IncidentAnalysisResult.limitations` so a human
  reviewer sees it.
- Response parsing/validation via the existing `structured_output.parse_incident_analysis()`. On
  `StructuredOutputError`, retry once with the validation error text appended to the prompt, then
  raise.
- Timeout + bounded retry around the Anthropic call using `tenacity` (already a dependency),
  matching AGENTS.md: "All HTTP calls require timeout, retry and error mapping."
- On exhausted retries / API failure, raise — do not silently fall back to `LocalAnalysisGateway`
  for an individual incident (see threat-assessment.md, Failure Scenarios). A failed analysis must
  surface as a failed collection run / failed API call, not as a mislabeled deterministic stub.
- Unit tests using a fake/mocked Anthropic client. No live API calls in CI or in the test suite.

Out of scope (tracked separately):

- Wiring the dormant `agents/` LangGraph pipeline (`intake -> retrieve -> investigate ->
  root_cause -> remediation -> critique -> security_review -> approval -> notify`). Every node in
  `agents/nodes/*.py` is currently a stub (`{"status": "pending_llm_gateway"}`) and `graph.py` is
  not imported anywhere outside its own test. Building this out is a separate, materially larger
  task per ADR-002 and is not a prerequisite for this one.
- `OpenAiGateway` (still a stub) and `embedding_provider` (separate setting, already
  OpenAI-backed for embeddings only — untouched by this task).
- General-purpose hostname / free-text PII redaction in `Sanitizer`. The current `Sanitizer` only
  redacts emails, RFC1918 private IPs, Windows user-profile paths, and `key=value` secret
  patterns — it has no pattern for hostnames or public IPs. This is a known, already-demonstrated
  gap (the test run on 2026-06-23 sent real employee-identifying hostnames and public IPs to the
  real Discord webhook because of it). This task adds public-IP redaction only (cheap, low risk to
  add) and explicitly documents residual hostname/free-text PII risk for the project owner to
  accept or block on — see threat-assessment.md. It does not attempt general PII detection.
- `evals/` dataset-based quality scoring of analysis output (separate backlog item).

## Data Flow (this task)

1. `AnalyzeIncident.execute()` retrieves evidence from `PgVectorRepository` (internal knowledge
   base content — runbooks etc. — not raw ESET data). Unchanged.
2. New: `incident.title` / `incident.summary` are sanitized and injection-checked before prompt
   construction.
3. `AnthropicGateway.analyze()` renders `incident_analysis.jinja2` with the sanitized incident and
   evidence excerpts, calls the Anthropic Messages API with a bounded timeout/retry, and validates
   the JSON response against `IncidentAnalysisResult`.
4. The result flows back through `AnalyzeIncident` unchanged to both `POST /api/v1/analyses/run`
   and the automatic `collect_and_notify_incidents` path. The port contract
   (`analyze(*, incident, evidence) -> IncidentAnalysisResult`) does not change, so neither caller
   needs to change.

## Non-goals

- No change to the Discord notification builder or the approval workflow.
- No change to which severities get human approval (still High/Critical, per ADR-003).
- No change to the `/api/v1/analyses/run` request/response contract.

## Required Verification (existing project gate, unchanged)

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-fail-under=85
uv run bandit -r src
uv run pip-audit
```

See `acceptance-criteria.md` for testable criteria and `threat-assessment.md` for the security
review. The residual PII risk decision (Option A: ship with current sanitizer plus public-IP
regex, accept residual hostname-PII exposure to Anthropic) was resolved by the project owner on
2026-06-23 — see threat-assessment.md for the full record.
