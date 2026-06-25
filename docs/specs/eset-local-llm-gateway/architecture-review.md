# Architecture Review: Local LLM Gateway (Ollama) Replacing Anthropic

Date: 2026-06-25
Role: claude / architecture_owner

## Scope

Reviewed codex's implementation against `task-spec.md` and all 30 items in
`acceptance-criteria.md`. Diff (`git diff --stat`): 5 modified files, 2 removed files, 2 new files,
114 insertions(+), 661 deletions(-) — `anthropic_gateway.py` (190 lines) and
`test_anthropic_gateway.py` (286 lines) removed outright; `ollama_gateway.py` and
`test_ollama_gateway.py` added. Every changed/added file's full diff or full content was read
directly by claude (`git diff`, `Read`), not taken from codex's self-report. Independently re-ran
the full verification gate (`ruff check`, `mypy src`, `pytest --cov`, `bandit -r src`,
`pip-audit`, `docker compose config --quiet`) plus both required grep checks — all results matched
`implementation-report.md`'s figures exactly (87.29% coverage, 122 mypy-clean source files, both
greps empty). Ran the project's `architecture-review` skill checklist (dependency direction /
domain purity) and `security-gate` skill checklist directly.

## 1. Architecture Impact

Compliant. `OllamaGateway` (`infrastructure/llm/ollama_gateway.py`) implements the same
`LlmGateway` Protocol `AnthropicGateway` implemented, in the same infrastructure layer, with the
same internal structure (sanitize → injection-check → render → call-with-retry → parse-and-validate
→ retry-once-on-validation-failure → append injection notice). No domain or application code
changed. Confirmed via the `architecture-review` skill check: `domain/` imports only stdlib
(`enum`, `dataclasses`, `hashlib`) plus internal domain modules — no infrastructure, FastAPI,
SQLAlchemy, LLM SDK, httpx, or Discord import anywhere under `domain/`; `application/` has no
direct `httpx`/`sqlalchemy`/`fastapi`/discord import (both checked via grep across the full tree,
not sampled). `OllamaGateway` itself correctly imports `httpx` (an infrastructure-layer concern)
and only domain entities (`Incident`, `RetrievedEvidence`, `IncidentAnalysisResult`) — dependency
direction points inward, unchanged from the pattern `AnthropicGateway` already established. The
`_get_llm_gateway()` factory change in `api/dependencies.py` is a straight swap (one `if` branch's
condition and constructor call), not a new abstraction. `collect_and_notify_incidents.py` and
`collect_and_notify_detections.py` are untouched (`git diff --stat` against both files: no output)
— confirmed the analyzer-exception asymmetry flagged in `threat-assessment.md` was correctly left
alone, per the task's explicit out-of-scope instruction.

## 2. Security Impact

Compliant, net risk reduction. Independently read `ollama_gateway.py` in full:
`Sanitizer.sanitize_text()` is still called on `title`/`summary` before prompt construction
(lines 79-80), `PromptInjectionFilter.contains_suspicious_instruction()` is still called on the
original (pre-sanitization) title/summary (lines 81-83) with the same limitations-append behavior
on a flagged result (lines 114-117), and the evidence-id grounding check
(`valid_evidence_ids = {...} | {_NO_EVIDENCE_ID}`, lines 88, 134-144) is reproduced verbatim from
`AnthropicGateway` — none of the three security-relevant behaviors from the original gateway were
weakened or dropped in the port. Transport-level: `response.raise_for_status()` (line 164) raises
immediately, uncaught by the retry loop, for any non-2xx Ollama response — `_RETRYABLE_OLLAMA_ERRORS`
(lines 31-35) covers only `httpx.ConnectError`/`ConnectTimeout`/`ReadTimeout`, matching the spec's
"don't retry on what looks like misconfiguration" requirement (AC18), verified directly in code,
not just in the test suite. No secret of any kind exists in this design — `ollama_base_url`/
`ollama_model`/`ollama_keep_alive` are not credentials; confirmed no `ANTHROPIC_API_KEY`-shaped
string remains anywhere (`grep -ri anthropic` across `src/`, `tests/`, `pyproject.toml`,
`.env.example`, `docker-compose.yml` — independently re-run by claude, zero matches, matching
`implementation-report.md`). The previously-accepted "Residual PII Risk to Third-Party LLM"
finding from `llm-anthropic-gateway/threat-assessment.md` no longer applies to the analysis path:
`ollama` is a same-Docker-network sibling container, not an internet-facing third party — this is
a genuine security improvement, not merely a lateral move, and is independently confirmed true by
the new `docker-compose.yml` service definition (no published port beyond the internal network,
no API key configuration surface at all). Ran the `security-gate` skill checklist directly
(secrets / personal-data leakage / unsafe automation / missing approval gates / prompt-injection
handling) — all five PASS; see `security-gate-report.md` for the full record. `gitleaks`/`semgrep`/
`trivy` are not installed in either claude's or codex's execution environment (confirmed: `which
gitleaks semgrep trivy` returns nothing on the host; codex's sandbox reported the same `exit 127`
for all three) — this is a pre-existing environment gap, not new to this task (the very first
Anthropic gateway's security-gate review hit the same gap per
[[project-eset-incident-ai]] memory). Independently re-ran `bandit -r src` (0 issues, 3888 LOC) and
`pip-audit` (no known vulnerabilities) — both clean and both matching codex's reported figures.

## 3. Data Impact

Compliant, and a net improvement over the gateway being replaced. No schema change, no migration,
no new persisted field. Incident `title`/`summary` and RAG evidence excerpts are still sanitized
exactly as before; the only change is *where* the sanitized payload is sent (an in-network Ollama
container instead of `api.anthropic.com`). See task-spec.md's "Net data-flow change" — independently
confirmed by reading the new `docker-compose.yml` `ollama` service: no `ports:` mapping to the host
beyond the Docker-internal network, so the model server is not reachable from outside this
deployment's own containers either.

## 4. Operational Impact

Compliant with the spec; the residual risk the spec already calls out (no `mem_limit` on the
`ollama` service in `docker-compose.yml`) is confirmed still present after implementation — this
was explicitly scoped as "not required to block this task" in `threat-assessment.md`, and that
judgment still holds: the shipped configuration pins `ollama_model` to the single empirically-safe
tag (`qwen2.5:7b-instruct-q4_K_M`), so the unmitigated gap only matters if that pin is bypassed
later, which is a process/discipline question rather than something this diff could close by
itself. `llm_timeout_seconds` default of `240.0` and `ollama_keep_alive` default of `0s` both match
the project-owner decisions recorded in `threat-assessment.md` exactly — confirmed in
`config.py`'s diff, not just in `.env.example`. `docker compose config --quiet` passes
(independently re-run), confirming the new service is syntactically valid; no container lifecycle
command was run by either claude or codex during this review, consistent with the task's explicit
no-deploy constraint — the manual/operational acceptance items (AC28-30 in `acceptance-criteria.md`,
requiring a live `ollama` compose service and a real end-to-end call) remain genuinely unperformed
and are correctly recorded as such in `implementation-report.md`'s Deviations section, not silently
skipped.

## 5. Required Tests

`tests/unit/test_ollama_gateway.py` (new) covers: success path, no-evidence sentinel, sentinel
alongside unrelated real evidence, transport-error retry-then-succeed, transport-error
exhausts-retries-and-raises, non-2xx-raises-without-retry, prompt-injection-flag-path,
sanitizer-applied-to-prompt (with an explicit assertion that the *raw* private IP still appears —
correctly reflecting the 2026-06-24 decision to stop masking IPs, not a leftover from the deleted
Anthropic test), and a Jinja2-autoescape/template-injection-safety test
(`{{ 7 * 7 }}` must appear literally, not evaluate to `49`). This matches or exceeds
`acceptance-criteria.md` items 6, 7, 14-19, 24-25. `test_dependencies.py`,
`test_detection_settings_and_celery.py`, and `test_llm_gateway_factory.py` were updated for the
new settings/factory shape — independently spot-checked that the factory test now exercises both
`ollama_model` set and cleared (AC8), not just the happy path.

## 6. Approval

**Approved.** `OllamaGateway` faithfully reproduces every security-relevant behavior of the
gateway it replaces while removing a secret and closing a third-party data-egress path entirely.
The one item this task deliberately left open — the Incident-vs-Detection analyzer-exception
asymmetry under a less reliable backend — was correctly left untouched per
`threat-assessment.md`'s explicit scoping and remains tracked there, not resolved here. Outstanding
before this is safe to deploy to the live `api`/`worker`/`scheduler` containers: the manual
end-to-end verification against a real, compose-managed `ollama` service (`acceptance-criteria.md`
AC28-30) has not yet been performed — this review approves the code change itself, not a
deployment decision, which remains a separate step requiring the project owner's go-ahead per
[[project-eset-incident-ai]]'s established "각 단계 별개 승인" pattern (commit → rebuild →
migrate/pull-model → live-verify, each its own checkpoint).
