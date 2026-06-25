# Task Spec: Local LLM Gateway (Ollama) Replacing Anthropic

Owner (specification): claude
Implementer: codex
Status: proposed — awaiting implementation

## Business Requirement

On 2026-06-24, `anthropic.BadRequestError: Your credit balance is too low` started appearing in
worker logs. From that point on, every Incident and Detection analysis call failed; notifications
still went out (existing graceful-degradation behavior in the Detection path, see Non-goals) but
with `analysis=None`, silently dropping the AI root-cause/remediation content the project depends
on. The project owner decided this dependency is unacceptable going forward — not "top up credits
and continue," but "stop depending on a metered third-party API for this capability entirely" —
and chose to self-host an LLM via Ollama on the existing `devops` host (no new hardware, no cloud
GPU; that hosting question was decided 2026-06-24).

A feasibility spike was run before this spec (2026-06-25, this session) directly against the
production prompt (`config/prompts/incident_analysis.jinja2`) and a realistic sample
incident+evidence payload, using the Ollama HTTP API on this host:

| Model | Quant | Disk size | Total latency | Output tok/s | JSON valid | Host impact |
|---|---|---|---|---|---|---|
| `qwen2.5:7b-instruct-q4_K_M` | Q4_K_M | 4.7 GB | 147.6 s (28.9 s prompt eval + 112.2 s gen) | ~6.5 | Yes, on first try | RAM 5.1 GB used, **no swap** |
| `qwen2.5:14b-instruct-q3_K_M` | Q3_K_M | 7.3 GB | 286.2 s | ~3.7 | Yes, on first try | RAM use pushed host into **1.6 GB swap**, available RAM dropped to 1.8 GB |
| `qwen3.5:35b(-a3b)` | Q4_K_M | ~24 GB | not run | n/a | n/a | **Rejected without running** — this host has 11 GB total RAM; loading would almost certainly OOM-kill processes, and this host also runs the production `api`/`worker`/`scheduler`/`postgres`/`redis` containers |

This host has no GPU (`nvidia-smi` absent) and 11 GB total RAM. The 14B run is not a viable
middle ground: going up one size tier made inference *slower* (not faster — there is no Q-level at
which a 14B model both fits comfortably and out-performs the 7B model on this hardware) and put
production containers at real risk of an OOM-driven crash. **`qwen2.5:7b-instruct-q4_K_M` is the
ceiling this host can run safely**, confirmed empirically, not assumed. Production containers
(`docker compose ps`) stayed healthy through both spike runs, but the 14B run left only 1.8 GB
available — close enough to a real incident that model size must be treated as a hard operational
constraint in this spec, not a tunable quality knob.

## Scope

In scope:

- **Remove `AnthropicGateway` entirely** (project owner decision, 2026-06-25 — explicitly chose
  full replacement over keeping both providers switchable, after being offered and declining the
  lower-risk "keep both" option):
  - Delete `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py` and
    `tests/unit/test_anthropic_gateway.py`.
  - Remove the `anthropic` SDK dependency from `pyproject.toml`.
  - Remove `anthropic_api_key`, `anthropic_model` from `Settings` (`settings/config.py`) and from
    `.env.example`.
  - Remove the `"anthropic"` branch of `_get_llm_gateway()` in `api/dependencies.py` along with the
    `AnthropicGateway` import.
- **Discard the uncommitted web-search work** (project owner decision, 2026-06-25, after being told
  explicitly that this throws away implemented-and-verified-but-never-shipped code): the working
  tree currently has uncommitted changes across 13 files implementing Anthropic's server-side
  `web_search_20250305` tool (`ExternalReference`/`external_references` on
  `domain/entities/analysis.py`, `llm_web_search_enabled`/`llm_web_search_max_uses` settings, the
  web-search branch in `anthropic_gateway.py`, rule 10 in `incident_analysis.jinja2`) plus
  `docs/specs/eset-llm-web-search/` (untracked). None of this was ever committed or deployed.
  Because `AnthropicGateway` is being deleted outright and Ollama/qwen2.5 has no equivalent
  server-side web-search tool, this capability has no home in the new design. Implementer should
  start from a clean `git checkout -- .` / removal of the untracked spec directory at
  `4d4d16a` (the last commit) before building the Ollama gateway, rather than trying to merge the
  new gateway on top of the discarded Anthropic changes.
- **New `OllamaGateway`** (`src/eset_incident_ai/infrastructure/llm/ollama_gateway.py`) implementing
  the same `LlmGateway` protocol (`application/ports/llm_gateway.py`) that `AnthropicGateway`
  implemented. Reuse the proven pieces from `AnthropicGateway` as-is, swapping only the transport:
  - Same `incident_analysis.jinja2` template, rendered the same way (`incident_json` +
    `evidence_list`).
  - Same `Sanitizer.sanitize_text()` call on `title`/`summary` before rendering.
  - Same `PromptInjectionFilter` check and `limitations` append behavior.
  - Same `structured_output.parse_incident_analysis()` validation, same evidence-id grounding check
    (`valid_evidence_ids = {evidence ids} | {_NO_EVIDENCE_ID}`), same retry-once-on-validation-
    failure pattern.
  - **Do not** name the new class `LocalAnalysisGateway` or reuse that file — that name is already
    taken by the existing deterministic non-LLM stub (`infrastructure/llm/local_gateway.py`), which
    stays exactly as-is and continues to serve as the no-provider-configured fallback.
  - Transport: `httpx` POST to `{ollama_base_url}/api/generate` with
    `{"model": ollama_model, "prompt": rendered_prompt, "stream": false, "format": "json",
    "keep_alive": ollama_keep_alive}`. Use Ollama's `format: "json"` constrained-output mode (this
    is what the feasibility spike used) rather than relying on prompt rule 8 alone.
  - Retry policy: `tenacity`, retrying only on connection/timeout errors (`httpx.ConnectError`,
    `httpx.ConnectTimeout`, `httpx.ReadTimeout`), matching the
    transport-errors-only-retry design `AnthropicGateway` already used. Ollama has no equivalent of
    a 429 rate limit or a 4xx "bad request" class in normal operation; a non-2xx HTTP response
    should raise immediately (likely a misconfiguration, e.g. wrong model name), not retry.
- **New Settings fields** (`settings/config.py`):
  - `ollama_base_url: str = "http://ollama:11434"`
  - `ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"` — pinned to the exact tag benchmarked in this
    spec. Changing this value to anything larger than 7B must go back through the same
    latency/swap/quality evaluation done here (see threat-assessment.md, "Model size is a hard
    constraint").
  - `ollama_keep_alive: str = "0s"` — unload the model immediately after each response (project
    owner decision, 2026-06-25: preserve host RAM headroom over avoiding the ~6–12 s reload cost
    measured in the spike's `load_duration`). Expressed as a setting, not hardcoded, so this can be
    tuned later without another code change if call patterns turn out to be bursty enough that
    reload overhead matters more than was estimated here.
  - `llm_provider: str = "ollama"` (was `"anthropic"`).
  - Raise `llm_timeout_seconds` default from `90.0` to `240.0` — the spike's 7B run took 147.6 s
    end-to-end; 90 s would have timed out it. 240 s leaves roughly 1.6x headroom over the measured
    figure for slower runs under load.
- **New `ollama` service in `docker-compose.yml`**, replacing the ad-hoc `ollama-test` container
  used only for this spec's benchmarking:
  ```yaml
  ollama:
    image: ollama/ollama
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama
  ```
  Add `ollama_data` to the top-level `volumes:` block. `api`/`worker`/`scheduler` do not need a
  `depends_on` entry for `ollama` — analysis failures are handled per the existing
  fail-closed/fail-open paths (see threat-assessment.md), the same way they don't `depends_on`
  the external ESET or Discord endpoints either. The model itself (`qwen2.5:7b-instruct-q4_K_M`,
  4.7 GB) is **not** baked into the image or auto-pulled by compose; document a one-time
  `docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M` step in
  `PROJECT_STATUS.md` / a new operational note, run once after first `up -d`.
- `_get_llm_gateway()` in `api/dependencies.py`: `"ollama"` branch returns `OllamaGateway(...)`
  when `settings.ollama_model` is set (it has a non-empty default, so this is effectively always
  true unless explicitly cleared); anything else still falls back to `LocalAnalysisGateway()`,
  preserving the existing "never silently construct a misconfigured gateway" invariant.
- Unit tests using a fake/mocked `httpx` transport (`respx`, already a dev dependency — used the
  same way `AnthropicGateway`'s tests mocked the Anthropic client). No live calls to a real Ollama
  server in CI.
- Update `PROJECT_STATUS.md`: remove Anthropic-specific verified-flow bullets, add the Ollama
  gateway and the one-time model-pull step, update "Remaining Future Enhancements" if needed.

Out of scope (tracked separately, see threat-assessment.md for the one decision required before
implementation):

- **The Incident-vs-Detection analyzer-exception-handling asymmetry.**
  `CollectAndNotifyIncidents._execute()` lets an analyzer exception propagate and abort the entire
  collection run (`collect_and_notify_incidents.py:91-96`, uncaught — the outer `execute()` at
  line 50-57 catches it only to record `collection_run_repository.save_failure()` before
  re-raising). `CollectAndNotifyDetections._analyze_detection()` instead catches per-detection and
  returns `analysis=None`, letting the run continue
  (`collect_and_notify_detections.py:186-204`). This was an intentional, accepted asymmetry when
  the backend was Anthropic (a paid API with an SLA); it is a materially bigger risk with a
  single-instance, CPU-bound, no-failover local model. **Not resolved by this task** — see
  threat-assessment.md's decision section. This task must not silently change Incident behavior
  while implementing the new gateway; whatever the project owner decides, it should land as an
  explicit, separate, reviewed change.
- GPU acceleration or any cloud-GPU hosting for the model — rejected by the project owner
  (2026-06-24 hosting decision, reaffirmed implicitly today by rejecting the 35B model rather than
  reopening that decision).
- Any model larger than `qwen2.5:7b-instruct-q4_K_M` on this host — empirically rejected in this
  spec (14B: slower and induces swap; 35B: not even attempted, certain OOM risk to production
  containers on the same host).
- Standing/always-loaded model (`OLLAMA_KEEP_ALIVE=-1`) — considered and explicitly rejected by the
  project owner in favor of on-demand loading, trading ~6–12 s of reload latency per call for
  keeping the host's ~5 GB of headroom free between calls.
- A replacement for the discarded web-search/external-vendor-research capability
  ([[eset-llm-web-search]], never committed). If this capability is wanted again later, it needs a
  new mechanism entirely (Ollama/qwen2.5 has no equivalent of Anthropic's server-side
  `web_search_20250305` tool) — out of scope for this task, not assumed to be revisited.
- Wiring the dormant `agents/` LangGraph pipeline (ADR-002) — unchanged from the original Anthropic
  gateway spec's scope decision; still all stubs, still not a prerequisite for this task.
- `OpenAiGateway` (still a stub, untouched) and `embedding_provider` (separate, OpenAI-backed,
  untouched — embeddings are not part of this task).

## Data Flow (this task)

1. `AnalyzeIncident.execute()` retrieves evidence from `PgVectorRepository` — unchanged.
2. `incident.title`/`incident.summary` are sanitized and injection-checked — unchanged from the
   Anthropic gateway's behavior, now performed inside `OllamaGateway` instead of `AnthropicGateway`.
3. `OllamaGateway.analyze()` renders `incident_analysis.jinja2` with the sanitized incident and
   evidence excerpts (identical rendering logic), then POSTs to the in-network `ollama` service
   (`http://ollama:11434/api/generate`) with `format: "json"`, a bounded timeout
   (`llm_timeout_seconds`), and `keep_alive` from settings. Response is parsed and validated via the
   existing `structured_output.parse_incident_analysis()` and evidence-id grounding check.
4. The result flows back through `AnalyzeIncident` unchanged to both `POST /api/v1/analyses/run`
   and the two `collect_and_notify_*` flows. The port contract (`LlmGateway.analyze(...)`) does not
   change, so no caller needs to change beyond the factory wiring in `dependencies.py`.

**Net data-flow change:** incident data sent for LLM analysis no longer leaves the deployment's
Docker network — `ollama` is a sibling container on the same compose network, not a third-party
API over the internet. This removes the outbound-to-third-party-LLM trust boundary crossing that
the original Anthropic gateway spec introduced (see threat-assessment.md — this closes, rather than
carries forward, that document's "Residual PII Risk to Third-Party LLM" finding for the LLM-analysis
path specifically; it does **not** change the separate, already-decided-open Discord exposure path).

## Required Verification (existing project gate, unchanged)

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-fail-under=85
uv run bandit -r src
uv run pip-audit
docker compose config --quiet
```

Plus, since this removes a dependency and a whole module: `grep -ri anthropic src/ tests/
pyproject.toml .env.example` should return nothing after this task ships.

See `acceptance-criteria.md` for testable criteria and `threat-assessment.md` for the security
review and the one open decision (Incident analyzer-exception-handling asymmetry) the project owner
must resolve before — or explicitly defer past — implementation.
