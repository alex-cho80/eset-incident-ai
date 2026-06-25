# Acceptance Criteria: Local LLM Gateway (Ollama)

Each item must be demonstrable by a passing automated test unless marked manual.

## Removal (Anthropic gone, not just unused)

1. `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py` and
   `tests/unit/test_anthropic_gateway.py` no longer exist.
2. `anthropic` is not present in `pyproject.toml` dependencies, and `uv run pip-audit` /
   `uv run bandit -r src` both pass without it.
3. `grep -ri anthropic src/ tests/ pyproject.toml .env.example docker-compose.yml` returns no
   matches.
4. `Settings` (`settings/config.py`) has no `anthropic_api_key` or `anthropic_model` field.
5. The uncommitted web-search diff (`ExternalReference`/`external_references` on
   `IncidentAnalysisResult`, `llm_web_search_enabled`/`llm_web_search_max_uses` settings, the
   web-search branch in the old `anthropic_gateway.py`, prompt rule 10, and
   `docs/specs/eset-llm-web-search/`) is fully gone — not merged into `OllamaGateway` in any form.
   `grep -ri web_search src/ tests/ config/prompts/` returns no matches.

## Functional

6. `OllamaGateway.analyze(incident=..., evidence=...)` returns an `IncidentAnalysisResult` that
   passes Pydantic validation (built through `structured_output.parse_incident_analysis`, not
   constructed ad hoc).
7. Every `EvidenceClaim` in the result has `evidence_ids` drawn only from the evidence IDs passed
   into `analyze()` plus the `"no-supporting-evidence"` sentinel — same grounding rule
   `AnthropicGateway` enforced, re-implemented identically (not weakened) in `OllamaGateway`.
8. With `settings.llm_provider == "ollama"` (the new default) and `settings.ollama_model` set (it
   has a non-empty default), `get_analyze_incident()`, `get_collect_and_notify_incidents()`, and
   `get_collect_and_notify_detections()` all wire `OllamaGateway`. With `ollama_model` explicitly
   cleared to `""`, all three wire `LocalAnalysisGateway` — no code path silently constructs an
   `OllamaGateway` pointed at an empty model string.
9. `POST /api/v1/analyses/run` and both `collect_and_notify_*` flows work unchanged at the
   call-site level — no signature or response-shape change to either.
10. The rendered prompt sent to Ollama is byte-for-byte the same template output `AnthropicGateway`
    would have produced for the same input (same `incident_analysis.jinja2`, same
    `incident_json`/`evidence_list` construction) — verified by a test comparing the captured
    request body's `prompt` field against the existing template-rendering test fixtures.

## Configuration

11. `ollama_base_url`, `ollama_model`, `ollama_keep_alive` are read from environment/`.env` via
    `Settings`, with the defaults specified in task-spec.md (`http://ollama:11434`,
    `qwen2.5:7b-instruct-q4_K_M`, `0s`). `ollama_model` defaulting non-empty is intentional (unlike
    `anthropic_api_key`, which defaulted empty because it was a secret) — there is nothing
    secret about a model tag.
12. `llm_timeout_seconds` default is `240.0` (raised from the Anthropic-era `90.0`), sourced from
    `Settings`, not hardcoded in `OllamaGateway`.
13. `docker-compose.yml` defines an `ollama` service with a named volume (`ollama_data`) for model
    storage, and `docker compose config --quiet` passes.

## Prompt / Data Handling

14. `incident.title` and `incident.summary` pass through `Sanitizer.sanitize_text()` before
    interpolation into the prompt — same test pattern as the original Anthropic gateway (incident
    containing an email and a private IP; rendered prompt must not contain the raw email — private
    IPs are intentionally *not* masked per the 2026-06-24 sanitizer decision, so the IP assertion
    from the original test must be dropped or inverted, not copy-pasted unchanged).
15. `PromptInjectionFilter.contains_suspicious_instruction()` is called on the same fields; a test
    with an injection string in `incident.summary` asserts `IncidentAnalysisResult.limitations`
    contains the existing injection notice, and that `analyze()` does not raise or skip analysis.
16. The request sent to Ollama uses `format: "json"` (Ollama's constrained-output mode) in addition
    to the prompt's own "return only JSON" instruction — not relying on the instruction alone,
    since smaller/quantized local models are more likely to ignore free-text formatting
    instructions than a frontier hosted model.

## Failure Handling

17. A simulated connection error (`httpx.ConnectError`/`ConnectTimeout`/`ReadTimeout`) retries per
    `llm_max_retries` via `tenacity`, then raises — it does not return a `LocalAnalysisGateway`-
    shaped result and does not silently mask the failure as success.
18. A non-2xx HTTP response from Ollama (e.g., model name typo'd, returns 404) raises immediately
    without retrying — mirrors `AnthropicGateway`'s "4xx is not retryable" design, adapted to
    Ollama's error shape.
19. A response that fails `IncidentAnalysisResult` validation triggers exactly one retry with the
    validation error appended to the prompt; a second consecutive failure raises
    `StructuredOutputError`. (Same test pattern as the original gateway — re-implement, don't
    weaken to zero or unbounded retries.)
20. Whatever the project owner decides for the Incident-vs-Detection analyzer-exception asymmetry
    (see threat-assessment.md) is implemented as a separate, explicitly-labeled change — this task
    does not change `collect_and_notify_incidents.py`'s exception handling as a side effect of
    swapping the gateway.

## Security

21. No secret-shaped value is introduced by this task (there is no Ollama API key in this
    self-hosted setup) — confirm `ollama_base_url`/`ollama_model`/`ollama_keep_alive` contain no
    credential material and are safe to log if needed.
22. `bandit -r src` and `pip-audit` both pass with `anthropic` removed and `httpx`-based
    `OllamaGateway` added (httpx is already a project dependency via other infra clients).
23. `docs/architecture/trust-boundaries.md` / `threat-model.md` do not need a "third-party LLM"
    update for the analysis path going forward (see task-spec.md "Net data-flow change") — confirm
    no stale Anthropic-specific language remains in those docs after this task.

## Testing

24. New unit tests cover: success path (mocked `httpx` transport via `respx`), retry-then-success
    on validation failure, exhausted-retries-raises (validation and connection-error cases),
    prompt-injection-flag-path, sanitizer-applied-to-prompt, `format: "json"` present in the request
    body, and the provider-selection factory (`ollama_model` set vs cleared).
25. No test makes a real network call to a live Ollama server. `respx` (already a dev dependency)
    or an injected fake client/transport is used, matching how `AnthropicGateway`'s tests mocked the
    Anthropic client.
26. `uv run pytest --cov=src --cov-fail-under=85` passes including the new code, with the deleted
    `anthropic_gateway.py` test file's coverage contribution replaced by the new `OllamaGateway`
    tests (net coverage should not regress).
27. `uv run mypy src`, `uv run ruff check .`, `uv run ruff format --check .` all pass.

## Manual / Operational (not automated)

28. A manual run against the real `ollama` compose service (not the ad-hoc `ollama-test` container
    used for this spec's feasibility spike) is performed once before merge, using the actual
    `docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M` startup procedure
    documented in task-spec.md, confirming `POST /api/v1/analyses/run` returns a schema-valid,
    Korean-language result end-to-end through the real container network (`http://ollama:11434`,
    not `localhost:11434`).
29. During that manual run, `docker compose ps` and `free -h` are checked before and after to
    confirm production containers (`api`/`worker`/`scheduler`/`postgres`/`redis`) stay healthy and
    available RAM does not drop into swap — repeating the same check this spec's feasibility spike
    already did for the 7B model on the ad-hoc container, now against the real compose-managed
    service.
30. Record the measured end-to-end latency from that run in the PR description, and confirm it is
    consistent with this spec's spike figure (147.6 s) within reasonable variance — a large
    deviation (e.g., 2x+ slower) should be investigated before merge rather than assumed to be
    noise.
