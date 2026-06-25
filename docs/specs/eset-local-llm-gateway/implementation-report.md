# Implementation Report: Local LLM Gateway (Ollama)

Date: 2026-06-25

## Files Changed, Added, Removed

Added:

- `src/eset_incident_ai/infrastructure/llm/ollama_gateway.py`
- `tests/unit/test_ollama_gateway.py`
- `docs/specs/eset-local-llm-gateway/implementation-report.md`

Removed:

- `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py`
- `tests/unit/test_anthropic_gateway.py`

Modified:

- `.env.example`
- `PROJECT_STATUS.md`
- `docker-compose.yml`
- `pyproject.toml`
- `uv.lock`
- `src/eset_incident_ai/api/dependencies.py`
- `src/eset_incident_ai/settings/config.py`
- `tests/unit/test_dependencies.py`
- `tests/unit/test_detection_settings_and_celery.py`
- `tests/unit/test_llm_gateway_factory.py`

Generated cleanup:

- Removed stale `__pycache__` directories under `src/` and `tests/` because their old bytecode
  contained removed provider strings and would make the required literal grep checks fail.

## Implementation Summary

- Removed the hosted provider gateway, tests, SDK dependency, lockfile entries, settings fields,
  environment example entries, and dependency-factory branch.
- Added `OllamaGateway` behind the existing `LlmGateway` port.
- `OllamaGateway` reuses the existing prompt template, sanitizer, prompt-injection filter,
  structured-output parser, evidence-ID grounding rule, and retry-once validation correction
  behavior.
- Ollama transport uses `httpx.AsyncClient` POST to `{ollama_base_url}/api/generate` with
  `model`, `prompt`, `stream: false`, `format: "json"`, and `keep_alive`.
- Transport retries are limited to `httpx.ConnectError`, `httpx.ConnectTimeout`, and
  `httpx.ReadTimeout`; non-2xx responses raise immediately via `response.raise_for_status()`.
- Added settings defaults:
  - `llm_provider = "ollama"`
  - `ollama_base_url = "http://ollama:11434"`
  - `ollama_model = "qwen2.5:7b-instruct-q4_K_M"`
  - `ollama_keep_alive = "0s"`
  - `llm_timeout_seconds = 240.0`
- `_get_llm_gateway()` now returns `OllamaGateway` only when `LLM_PROVIDER=ollama` and
  `OLLAMA_MODEL` is non-empty; otherwise it falls back to `LocalAnalysisGateway`.
- Added the `ollama` compose service and `ollama_data` named volume.
- Updated `PROJECT_STATUS.md` with Ollama operational notes, the one-time model pull command, and
  latest verification results.
- Left `collect_and_notify_incidents.py` exception handling unchanged, per the out-of-scope
  decision in `threat-assessment.md`.

## Verification Gate Results

Final gate run:

- `uv run ruff format --check .`: PASS, `169 files already formatted`
- `uv run ruff check .`: PASS, `All checks passed!`
- `uv run mypy src`: PASS, `Success: no issues found in 122 source files`
- `uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=85`: PASS,
  `179 passed in 2.90s`, total coverage `87.29%`
- `uv run bandit -r src`: PASS, `No issues identified`, `3888` lines of code scanned, severity
  counts Undefined/Low/Medium/High all `0`
- `uv run pip-audit`: PASS, `No known vulnerabilities found`
  - Note: pip-audit skipped the local project package itself because `eset-incident-ai (0.1.0)` is
    not on PyPI.
  - Environment warning: pip/pip-audit home-cache directories were read-only; this affected cache
    writes only, not the audit result.
- `docker compose config --quiet`: PASS, no output

During development, the first pytest run failed on test isolation and respx sequencing. Those were
fixed before the final gate above:

- Public dependency-factory tests now explicitly set `LLM_PROVIDER`/`OLLAMA_MODEL` so local `.env`
  values cannot override expected test state.
- One existing settings-default test now passes `_env_file=None` so local `.env` does not override
  default assertions.
- The exhausted transport retry test now uses explicit respx exception instances rather than a
  generator that terminates after raising.

## Required Grep Confirmations

Command:

```bash
grep -ri anthropic src/ tests/ pyproject.toml .env.example docker-compose.yml
```

Result: PASS. No output, exit code `1` from grep due to no matches.

Command:

```bash
grep -ri web_search src/ tests/ config/prompts/
```

Result: PASS. No output, exit code `1` from grep due to no matches.

Additional stale-reference scan:

```bash
rg -n "Anthropic|anthropic|web_search" src tests config/prompts pyproject.toml .env.example docker-compose.yml PROJECT_STATUS.md docs/architecture uv.lock
```

Result: no output.

## Deviations

- No functional deviation from the implementation spec.
- Verification commands were run with `UV_CACHE_DIR=/tmp/uv-cache` because the default uv cache
  path under `/home/devops/.cache/uv` is read-only in this sandbox. The command bodies and results
  are otherwise the requested gate.

## Live Deployment Verification (claude, 2026-06-25, after implementation/review approval)

Performed after this report's implementation pass and after `architecture-review.md`/
`security-gate-report.md` approval, as a separate deploy step (project-owner confirmed at each
stage):

1. `docker compose up -d --build api worker scheduler ollama` — all 5 production containers
   (`api`/`worker`/`scheduler`/`postgres`/`redis`) plus the new `ollama` service came up healthy.
2. `docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M` — succeeded, 4.7 GB pulled
   into the `ollama_data` volume.
3. **First live call used the wrong backend silently-by-design**: the live `.env` (not
   `.env.example`) still had `LLM_PROVIDER=anthropic` from before this migration, so
   `_get_llm_gateway()` correctly fell back to `LocalAnalysisGateway` (the deterministic stub) per
   AC8 — confirmed by the response's `executive_summary` matching `local_gateway.py`'s f-string
   exactly. This is not a code defect; it is `.env` having never been updated for this task (only
   `.env.example` is part of the diff). Fixed by editing the live `.env`: `LLM_PROVIDER=ollama`,
   added `OLLAMA_BASE_URL`/`OLLAMA_MODEL`/`OLLAMA_KEEP_ALIVE`, raised `LLM_TIMEOUT_SECONDS` to
   `240`, and removed the now-dead `ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` lines (project-owner
   confirmed both the fix and the key removal). Re-ran `docker compose up -d --build api worker
   scheduler` so the new `.env` was actually picked up (per the known "`restart` doesn't reread
   `.env`" finding).
4. Second live call (`POST /api/v1/analyses/run`, real incident through the real `AnalyzeIncident`
   → `OllamaGateway` → `http://ollama:11434/api/generate` path, not the ad-hoc benchmarking setup
   from the feasibility spike): **200 OK in 182.5 s** (vs. 147.6 s in the spike — within reasonable
   variance, no investigation triggered per AC30's threshold). Schema-valid JSON, fluent Korean
   natural-language fields, `priority` enum literals correctly left in English, and correct
   evidence-grounding behavior — no RAG evidence was retrieved for this synthetic test incident, so
   every claim correctly cited the `no-supporting-evidence` sentinel rather than a fabricated ID.
5. All 5 production containers stayed healthy throughout both calls. Host memory after the second
   call: 8.9 GB available, swap at 1.0 GB (model unloads per `keep_alive=0s` after each call) — no
   sign of the resource pressure seen in the rejected 14B feasibility test.

This satisfies `acceptance-criteria.md` AC28 (real compose-managed run, schema-valid Korean output),
AC29 (production containers stayed healthy and available, checked before/during/after), and AC30
(latency recorded and within reasonable variance of the spike figure).
