# Threat Assessment: Anthropic LLM Gateway

Owner: claude (architecture/security review, per harness.yaml)
Status: one decision below requires explicit project-owner sign-off before implementation starts.

## What changes

Today, no incident data leaves the deployment: `LocalAnalysisGateway` is a local deterministic
stub. This task introduces the **first outbound transmission of incident data to a third-party
API** (Anthropic) in this system's history. That is a new trust boundary crossing and needs to be
treated as such, consistent with `docs/architecture/trust-boundaries.md` and
`docs/architecture/threat-model.md`.

## Assets in scope

- ESET incident free text (`displayName`, `description`) — observed in this environment to
  contain employee names, internal site identifiers, employee IDs, and public IP addresses (see
  Precedent below).
- Internal knowledge base excerpts (`knowledge/runbooks/*.md`) retrieved as RAG evidence — lower
  sensitivity, authored internally, not expected to contain PII.
- The Anthropic API key (secret).

## Precedent (why this is not hypothetical)

During manual verification of this system on 2026-06-23, a real collected ESET incident was
delivered to the real Discord webhook. Its `description` field contained, unredacted: three
employee names with site names and employee IDs (e.g. `남부2지점-김정수-240085`), and three public
IP addresses. The Discord message's own footer claimed "Sanitized ESET incident notification. Raw
identifiers are not included" — that claim was false for this message. Root cause: `Sanitizer`
(`security/sanitizer.py`) only matches emails, RFC1918 private IPs, Windows user-profile paths, and
`key=value` secret strings. It has no pattern for hostnames or public IPs. The project owner was
informed and explicitly decided to leave the already-sent Discord message and the Discord-bound
sanitizer gap as-is for now.

This task reuses the same `incident.summary` field as the Discord path and feeds it to a *new*
recipient (Anthropic) with the *same* sanitizer. Without changes, the same category of data
exposure will recur on every analysis call, this time to a US-based third party rather than an
internal Discord channel the project owner already controls.

## Threats

Mapped to the existing categories in `docs/architecture/threat-model.md`:

| Threat | Applies here? | Mitigation in this task |
|---|---|---|
| Secret exposure through logs/prompts | Yes — new: Anthropic API key, and the prompt itself if logged | Key sourced from env only, never logged; avoid logging full rendered prompts (log a hash/length instead if prompt logging is needed for debugging) |
| Prompt injection embedded in incident fields | Yes | `PromptInjectionFilter` check (best-effort, not a hard block) + prompt instructs model to ignore embedded instructions (already proven pattern in `root_cause_analyst.jinja2`) |
| Cross-tenant retrieval leakage | No change — `tenant_scope` filtering is unchanged, already handled by `PgVectorRepository.search` | N/A to this task |
| Unsupported LLM claims presented as fact | Yes | Schema requires `evidence_ids` on every claim (existing `IncidentAnalysisResult` constraint); acceptance criteria #2 requires a deliberate, tested policy on fabricated evidence IDs |
| Unsafe recommendations without approval | No change — `requires_approval` / severity-based human approval gate (ADR-003) is unchanged downstream of this task | N/A to this task |
| **PII/identifier exposure to a third party** (not explicitly named in threat-model.md as "third party" but covered by "Sanitization... before external transmission") | **Yes — new and unresolved**, see decision below | Partial: sanitizer reused as-is, plus public-IP pattern added |

## Residual PII Risk to Third-Party LLM — decision required

The existing `Sanitizer` cannot detect hostnames embedded in free text (the exact gap that caused
the Discord exposure above). Building a reliable general-purpose hostname/PII detector is a
materially larger effort than this task (false positives/negatives in free text are hard to bound)
and is explicitly out of scope per task-spec.md.

Options, for the project owner to choose between before Codex implements:

- **A — Accept residual risk, ship with current sanitizer + public-IP regex only.** Consistent
  with the decision already made for the Discord path. Fastest. Residual risk: incident
  descriptions containing hostname-embedded employee identifiers will reach Anthropic's API
  unredacted, same as they reached Discord.
- **B — Exclude `incident.summary` (raw ESET description) from the prompt entirely for this MVP;
  send only `title`, `severity`, `status`, timestamps, and internal RAG evidence excerpts.**
  Meaningfully reduces exposure (the PII observed so far was in `description`, not `displayName`)
  at the cost of analysis quality — the model loses the most detailed signal. Still not a
  guarantee, since `displayName` could theoretically carry identifiers too.
  - Note: Anthropic does not train on API inputs/outputs by default and offers data retention
    controls — the project owner may want to confirm current contractual/DPA terms separately if
    this materially changes the risk calculus. That confirmation is outside this repo's scope.
- **C — Block this task until `Sanitizer` is extended with an organization-specific hostname
  pattern** (e.g., a regex for the observed `<site>-<name>-<employee-id>` convention, if that
  convention is fixed and known in advance). Slowest, but closes the actual gap rather than
  routing around it.

This document does not pick one of A/B/C on the project owner's behalf — unlike the
LangGraph-scope and prompt-design calls above, this one trades off real PII exposure against
delivery speed and analysis quality, which is the project owner's call to make, not an engineering
default.

**Decision (2026-06-23): Option A.** Project owner accepts the residual risk. Ship with the
current `Sanitizer` plus the public-IP regex addition only. `incident.summary` (raw ESET
description) is sent to Anthropic best-effort-sanitized; hostname-embedded identifiers (the same
category that reached Discord unredacted) may still reach Anthropic's API. No further sanitizer
work is required before this task ships. Revisit if the residual risk becomes unacceptable later
(e.g., before a wider rollout, or if this system starts handling a different data sensitivity
class).

## Review Output (per CLAUDE.md)

1. **Architecture impact** — Adds one new infrastructure adapter (`AnthropicGateway`) behind the
   existing `LlmGateway` port; no domain or application code changes; no new inward dependency
   from domain on infra/LLM SDK. Adds a provider-selection factory to `api/dependencies.py`
   (currently has none — `LocalAnalysisGateway` is hardcoded in two places).
2. **Security impact** — New third-party data egress path. Mitigated by reusing
   sanitizer/injection-filter (with known gaps, see decision above), bounded retries, no key
   logging, no fallback-masking of failures.
3. **Data impact** — Incident `title`/`summary` and RAG evidence excerpts leave the deployment
   boundary for the first time, going to Anthropic's API. No data is persisted by this task beyond
   what `AnalyzeIncident`/`IncidentAnalysisResult` already persist today.
4. **Operational impact** — New external dependency (Anthropic API availability/latency) on the
   critical path of both `/api/v1/analyses/run` and the scheduled `collect_and_notify_incidents`
   job. Failure mode is fail-closed (raise, record collection-run failure) rather than silent
   degradation to stub output — consistent with `docs/runbooks/llm-provider-failure.md` ("fail
   closed for high/critical incidents"). Recommend updating that runbook once real failure modes
   (rate limits, timeouts) are observed in practice.
5. **Required tests** — See acceptance-criteria.md, items 16-20.
6. **Approval** — Approved. The project owner resolved the "Residual PII Risk to Third-Party LLM"
   decision as Option A (2026-06-23). Implementation may proceed. No other blocking concerns.
