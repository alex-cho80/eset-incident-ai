# Threat Assessment: Local LLM Gateway (Ollama) Replacing Anthropic

Owner: claude (architecture/security review, per harness.yaml and `CLAUDE.md`)
Status: one decision below requires explicit project-owner sign-off before implementation starts.

## What changes

This task removes the only outbound-to-third-party-API trust boundary crossing in this system
(`AnthropicGateway`, added by `docs/specs/llm-anthropic-gateway/`) and replaces it with a
same-Docker-network call to a self-hosted Ollama container. It also removes the Anthropic API key
as a secret this system holds at all, and removes the never-shipped web-search capability
(`docs/specs/eset-llm-web-search/`) that depended on Anthropic specifically.

## Assets in scope

- ESET incident free text (`displayName`, `description`) — same sensitivity as before (see
  precedent in `docs/specs/llm-anthropic-gateway/threat-assessment.md`: known to contain employee
  names/site identifiers/employee IDs and public IPs in practice).
- Internal knowledge base excerpts (RAG evidence) — unchanged, low sensitivity.
- The Ollama container itself, and the host it runs on (new asset class for this threat model: a
  self-hosted model server with real resource limits, rather than an external API with someone
  else's capacity behind it).

There is **no API key asset** in this design — that line item from the original Anthropic
threat-assessment is removed, not just mitigated.

## Net positive: third-party data egress for LLM analysis is eliminated

The original Anthropic gateway threat-assessment's central unresolved item was "Residual PII Risk
to Third-Party LLM" — accepted by the project owner as Option A (ship as-is, accept the risk) on
2026-06-23, then widened on 2026-06-24 when private/public IP masking was removed from the shared
sanitizer entirely. Every incident analysis call has, since then, sent raw IPs (and whatever
hostname/employee-identifier text the sanitizer still misses) to Anthropic's API in the US.

This task closes that specific exposure path for LLM analysis: `ollama` is a sibling container on
the same Docker Compose network, not a third-party endpoint over the internet. Incident data used
for analysis no longer leaves the deployment boundary. This does **not** change the Discord
exposure path (`docs/specs/llm-anthropic-gateway/threat-assessment.md`'s original 2026-06-23
precedent finding, and the 2026-06-24 IP-masking-removal decision) — that is a separate boundary
the project owner has already and separately decided to accept risk on. Do not conflate the two
when reporting this task's security impact; only the LLM-analysis egress path is affected.

## Threats

Mapped to `docs/architecture/threat-model.md`:

| Threat | Applies here? | Mitigation in this task |
|---|---|---|
| Secret exposure through logs/prompts | **No longer applies to LLM analysis** — no API key exists in this design. `ollama_base_url`/`ollama_model` are not secrets. | N/A |
| Prompt injection embedded in incident fields | Yes, unchanged | Same `PromptInjectionFilter` check, same prompt framing (instructions to ignore embedded text), reused as-is from `AnthropicGateway` |
| Cross-tenant retrieval leakage | No change | N/A to this task |
| Unsupported LLM claims presented as fact | Yes, unchanged — and arguably higher risk with a smaller model | Same evidence-id grounding check reused as-is; see "Quantized-model reliability" below for why this matters more now |
| Unsafe recommendations without approval | No change — severity-based human approval (ADR-003) is unchanged | N/A to this task |
| PII/identifier exposure to a third party | **Eliminated for the LLM-analysis path** (see above) | N/A — this task removes the threat rather than mitigating it |
| **New: local model availability/resource exhaustion** | **Yes — new, see decision below** | Partial: model size pinned to the empirically-safe 7B tier; on-demand loading (not always-loaded) to preserve host headroom |
| **New: Incident-vs-Detection failure-mode asymmetry under a less reliable backend** | **Yes — new and unresolved, see decision below** | Not mitigated by this task; flagged for project-owner decision |

## New risk: local model availability and host resource exhaustion

Unlike Anthropic (a paid API backed by someone else's capacity and SLA), the new `ollama` service
is a single container on the same host as the production `api`/`worker`/`scheduler`/`postgres`/
`redis` containers, with no failover and a hard resource ceiling this team directly owns. This
spec's feasibility spike demonstrated the ceiling concretely, not theoretically:

- `qwen2.5:7b-instruct-q4_K_M` (the chosen model): 147.6 s per call, 5.1 GB RAM, **no swap**.
  Production containers stayed healthy.
- `qwen2.5:14b-instruct-q3_K_M` (tested as a possible quality/speed middle ground, then rejected):
  286.2 s per call (slower, not faster, despite more aggressive quantization), pushed the host into
  1.6 GB of swap, dropped available RAM to 1.8 GB. Production containers stayed healthy *this
  time*, but with materially less margin than is safe to rely on repeatedly.
- `qwen3.5:35b`: not attempted at all. At ~24 GB (Q4_K_M) against this host's 11 GB total RAM,
  loading it would almost certainly trigger an OOM kill — of the Ollama process at best, of a
  production container at worst, on a shared host with no memory cgroup isolation configured
  between services in `docker-compose.yml` today.

**Mitigation in this task:** `ollama_model` is pinned to `qwen2.5:7b-instruct-q4_K_M` specifically
(not "whatever is biggest that fits," not a user-overridable "just try a bigger one" knob without
re-running this evaluation). `ollama_keep_alive=0s` (on-demand loading, project-owner decision
2026-06-25) keeps the host's ~5 GB of headroom free between calls rather than committing it
permanently — the explicit trade-off accepted is per-call reload latency (+6–12 s, measured) in
exchange for not permanently shrinking the host's available memory the other production containers
also depend on.

**Residual risk, not fully mitigated by this task:** there is still no hard memory limit configured
on the `ollama` container in `docker-compose.yml` (no `mem_limit`/`deploy.resources.limits` in the
proposed compose service in task-spec.md). If a future change to `ollama_model` (accidental or
deliberate, bypassing the pinning convention above) loads a larger model, nothing in Docker itself
will stop it from taking down sibling containers via host-level OOM the same way an unconstrained
process on bare metal would. Adding `docker-compose.yml` memory limits for `ollama` (and ideally
for the other services too) is a reasonable follow-up; it is called out here rather than silently
assumed, but is **not required to block this task** since the pinned-model mitigation above is
sufficient for the model actually being shipped.

## Decision required: Incident-vs-Detection analyzer-exception asymmetry

`CollectAndNotifyIncidents._execute()` (`collect_and_notify_incidents.py:91-96`) calls
`self._analyzer.execute(...)` with no surrounding `try`/`except`. An exception there propagates out
of `_execute()`, is caught only by the outer `execute()` wrapper
(`collect_and_notify_incidents.py:50-57`), which records a collection-run failure and re-raises.
**Net effect: one bad analysis call aborts the entire Incident collection run** — every other
incident in that batch, including ones that needed no analysis-affecting decision at all, goes
uncollected and unnotified.

`CollectAndNotifyDetections._analyze_detection()` (`collect_and_notify_detections.py:186-204`)
instead wraps the analyzer call in its own `try`/`except Exception`, logs a warning, and returns
`None` — the detection is still notified, just without AI analysis attached. **Net effect: one bad
analysis call affects only that one detection.**

This asymmetry was an accepted, intentional design choice when the backend was Anthropic — a paid
API with a published SLA, where a transient analyzer failure was a reasonable signal that
something else (rate limiting, an outage) was wrong enough to warrant stopping and surfacing it
loudly for Incidents specifically (per
`docs/runbooks/llm-provider-failure.md`: "fail closed for high/critical incidents"). It was not
revisited when Detections was built ([[project-eset-incident-ai]] memory notes this was a
deliberate divergence from Incident behavior, chosen because Detection volume is 2-3 orders of
magnitude higher and a livelock risk from retrying the same cursor position forever was judged
worse than silently degrading individual records).

The backend is now a single-instance, CPU-bound, no-failover local container that this spec already
demonstrated can be pushed into swap by an oversized model, and has no SLA at all. The
cost/benefit of "abort the whole Incident run on one analyzer failure" is different with this
backend than it was with Anthropic — but this task does not resolve which way it should change, for
the same reason the original Anthropic spec didn't resolve its PII-risk decision unilaterally: it's
a deliberate trade-off between fail-closed safety guarantees and operational resilience, not an
engineering default to assume silently.

Options, for the project owner to choose between before Codex implements `OllamaGateway`:

- **A — Leave Incident behavior as-is (whole-run-abort on analyzer failure).** No code change to
  `collect_and_notify_incidents.py` in this task (matches the current task-spec.md scope, which
  already lists this as out of scope by default). Risk: a single slow/failed Ollama call (e.g., the
  host briefly under memory pressure from something unrelated) drops an entire batch of Incidents,
  including ones with no analysis-quality concern at all — more disruptive than it was with
  Anthropic, where this failure mode was rarer.
- **B — Align Incidents with Detections' per-record catch (`analysis=None`, keep notifying).**
  Closes the new resilience gap; matches the precedent already set for Detections. Trade-off:
  weakens the existing "fail closed for high/critical incidents" runbook guidance for the *analysis*
  step specifically — though note severity-based human-approval routing for High/Critical incidents
  happens **before** the analyzer is even called in `_execute()` (`collect_and_notify_incidents.py:
  77-83`), so this option would only affect Low/Medium auto-notify, not the approval-gated path.
  This needs its own task-spec/acceptance-criteria/threat-assessment trio (mirroring how the
  Detection field-mapping and severity-enum fixes each got their own spec) since it changes
  `collect_and_notify_incidents.py` behavior independent of the gateway swap — not bundled into this
  task's diff.
- **C — Keep whole-run-abort, but make it cheaper to recover from.** E.g., persist progress so a
  re-run after a transient Ollama failure resumes rather than reprocessing the whole batch. Larger
  effort, not scoped here.

This document does not pick one of A/B/C on the project owner's behalf. Recommendation, if asked:
B is the smallest change that meaningfully reduces the new risk this task introduces, and it
reuses an already-proven pattern from the same codebase rather than inventing a new one — but it is
explicitly a recommendation, not the decision.

**Decision: _pending_.** Implementation of `OllamaGateway` itself (this task) does not depend on
this decision and may proceed under Option A (today's default, unchanged) in the interim;
whichever option is chosen should land as its own follow-up change once decided, not retrofitted
silently into this task's PR.

## Review Output (per CLAUDE.md)

1. **Architecture impact** — Replaces one infrastructure adapter behind the existing `LlmGateway`
   port (`AnthropicGateway` → `OllamaGateway`) with no domain or application code changes beyond
   the factory wiring in `dependencies.py`. Adds one new Docker Compose service (`ollama`) with no
   new inward dependency from domain/application on infrastructure.
2. **Security impact** — Net reduction: removes a secret (Anthropic API key) and removes the only
   third-party data egress path for LLM analysis. Adds a new (different-shaped) resource-exhaustion
   risk class, mitigated by pinning the model to the empirically-validated 7B tier and using
   on-demand loading — see "New risk" section above for the residual gap (no Docker memory limit
   configured).
3. **Data impact** — Incident `title`/`summary` and RAG evidence excerpts stay inside the
   deployment boundary for analysis going forward, reversing the original Anthropic gateway's
   data-impact finding for this specific path. No change to what is persisted.
4. **Operational impact** — Replaces an external-API dependency (Anthropic rate limits/outages/
   billing) with a local, single-instance dependency (this host's RAM/CPU ceiling, empirically ~7B
   parameters at Q4 quantization). Per-call latency increases substantially (was effectively
   seconds with Anthropic; is ~150 s now) — `llm_timeout_seconds` raised accordingly
   (task-spec.md). Throughput is now bounded by this host's single CPU-bound inference slot (no
   GPU, no batching) rather than Anthropic's much higher concurrent-request capacity; if either
   collection job's per-run analysis volume grows materially, this ceiling will need revisiting
   before volume, not after a livelock or backlog is observed (cf. the Detection backlog-drain
   incident this same memory thread already lived through once, for a different root cause).
5. **Required tests** — See acceptance-criteria.md, items 1-27 (automated) and 28-30 (manual).
6. **Approval** — **Conditionally approved.** `OllamaGateway` implementation may proceed under the
   scope in task-spec.md. The Incident-vs-Detection analyzer-exception asymmetry above is an open
   decision that does not block this task (Option A, the status quo, applies by default) but must
   be tracked and not silently resolved as a side effect of this PR.
