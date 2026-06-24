# Threat Assessment: ESET Detections Ingestion

Owner: claude (architecture/security review, per harness.yaml)
Status: decisions below were already resolved by the project owner through direct questioning
(2026-06-24), recorded here for traceability rather than left open.

## What changes

Today, this system's only outbound view of ESET security data is `/v2/incidents` — a small,
already-curated set, and the existing severity-enum fix already established that HIGH/CRITICAL
Incidents correctly trigger Discord notification + human approval. This task adds a second,
much-higher-volume ESET data source (`/v1/detections`, 314k+ records and growing) into the same
notification/approval pipeline, and introduces a new policy exception: two specific fields
(`userName`, `device`) are sent to Discord **unmasked**, where Incidents currently mask nothing of
the kind by name (Incidents have no equivalent fields today) but the project's prior precedent
already shows raw IP addresses in Discord (see
`docs/specs/llm-anthropic-gateway/threat-assessment.md`'s "Precedent" section, documenting a
pre-existing sanitizer gap on hostnames/public IPs in the Incident path).

## Assets in scope

- ESET Detection free text (`displayName`, `context`, `objectName`, `objectUrl`) — same untrusted
  category as Incident `displayName`/`description`.
- ESET Detection identifying fields newly introduced by this task: `userName`, `device` (hostname).
  Per CLAUDE.md, these fall squarely in the protected category ("Never send raw usernames, ...,
  hostnames, ... to Discord without policy approval") — this task is exactly that policy-approval
  request, and the project owner has already granted it (see Decision below).
- `objectHashSha1` — a file hash. Not in CLAUDE.md's protected list (usernames/emails/hostnames/
  IPs/tokens/file paths); hashes are one-way identifiers of file content, not of a person or
  machine, and are safe to show raw, consistent with how `severity`/`category` are already shown
  raw.
- The persisted ESET pagination cursor (`last_page_token`) — opaque, ESET-issued, not a secret, but
  if corrupted could cause the run to skip or re-fetch large ranges; treated as integrity-sensitive
  operational state, not confidentiality-sensitive.

## Threats

Mapped to the same categories used in `docs/specs/llm-anthropic-gateway/threat-assessment.md`:

| Threat | Applies here? | Mitigation in this task |
|---|---|---|
| Secret exposure through logs | No new secret introduced (same ESET credentials, same host) | N/A |
| Prompt injection embedded in Detection free text | Low — Detections do not currently flow to the LLM analyzer (`AnalyzeIncident` is Incident-specific; this task does not wire an analyzer for Detections) | Out of scope for this task; if a future task adds LLM analysis of Detections, it must apply `PromptInjectionFilter` exactly as the Incident path does |
| **Raw PII (username/hostname) sent to Discord** | **Yes — new, by design** | Project owner explicitly authorized this exact exposure for exactly these two fields (see Decision). Implementation must scope the raw-bypass to only `userName`/`device`, not blanket-disable the sanitizer for the whole payload — enforced by acceptance-criteria.md items 16-17 |
| Unsafe recommendations without approval | No change — HIGH/CRITICAL still requires human approval, now also for Detections | `pending_detection_approvals` gate mirrors the existing Incident gate exactly |
| Cursor/pagination integrity (new) | Yes — a corrupted/invalid cursor could cause incorrect skip/replay behavior | Fail loudly (`save_failure`) rather than guess-and-recover; safety cap on pages-per-run bounds worst-case impact of a cycling token |
| Volume-driven resource exhaustion (new) | Yes — 314k+ records is three orders of magnitude larger than the Incident dataset | `detection_max_pages_per_run` safety cap; skip-zone logic avoids ever materializing the full backlog into notifications/approvals |

## Decision: Raw `userName`/`device` Exposure to Discord — already resolved

Unlike the Anthropic-gateway task's "Residual PII Risk" decision (which was left open in that
spec for the project owner to choose among options A/B/C), this decision was already made through
direct clarification before this spec was written, via `AskUserQuestion`:

> userName/device 둘 다 원래값 (both userName and device should be raw/unmasked)

**Decision (2026-06-24): both `userName` and `device` are sent to Discord raw/unmasked.** This
extends the existing precedent that IP addresses are already shown as-is in Incident notifications
(`SanitizedIncidentNotificationBuilder`'s footer text: "IP addresses and other identifiers are
shown as-is"). Email addresses remain pseudonymized (`Sanitizer.sanitize_text`'s `EMAIL_RE`) for
both Incidents and Detections — this task does not change that.

This is a narrower, more deliberate exception than the Anthropic-gateway precedent (which accepted
an *unintentional* sanitizer gap on hostnames/public IPs as residual risk). Here, the exposure is
*intentional and named* — exactly two fields, explicitly approved, implemented as an explicit
allowlist (not an accidental gap) in `SanitizedDetectionNotificationBuilder`. The implementation
must make this allowlist easy to audit: e.g., a single named constant or a short, commented list of
the exact field names that bypass sanitization, not a structural "skip sanitizer for this whole
builder" shortcut — so a future reviewer can see at a glance that the exception is scoped to
exactly what was approved.

Residual risk accepted by the project owner: Discord channel members will see raw employee
usernames and raw device hostnames for every HIGH/CRITICAL Detection. This is materially similar in
kind (not in root cause) to the already-accepted IP-address exposure — both are "operationally
useful identifiers an analyst needs to triage quickly," which is the standard precedent this
project has already established for trading some PII exposure for analyst usability in this
specific internal Discord channel.

## Volume / Operational Risk — flagged for review, not blocking

`/v1/detections` is ~3 orders of magnitude larger than `/v2/incidents` and growing continuously
(observed ~278 new records in a ~15-minute window during investigation — a single noisy sample, not
a validated sustained rate). Two related defaults in task-spec.md are engineering judgment calls,
not project-owner decisions, and should be confirmed/tuned after observing real production volume:

- `detection_notify_cron_interval_minutes = 60` (hourly, vs. Incidents' once-daily) — chosen
  because a daily cadence at observed volume could fall significantly behind.
  `detection_notify_limit = 500` per run is a companion default, not independently validated.
- `detection_max_pages_per_run = 1000` — sized to clear the entire current backlog (~315 pages) in
  a single run with headroom, so the very first run does not need multiple days to finish the
  skip-phase.

These are reversible config values (no migration/schema implication), so they are not treated as
blocking the spec — but the implementer (codex) and the project owner should revisit them once
real post-launch volume is observed, per acceptance-criteria.md item 29.

## Review Output (per CLAUDE.md)

1. **Architecture impact** — Adds one new vertical slice (client, entity revision, use case,
   notification builder, two new tables/ports, Celery task, API routes) parallel to the existing
   Incident slice, plus one shared generalization (`Severity.parse()`) and reuse of two existing
   entity-agnostic components (`NotificationRepository`/`notification_deliveries`, `Notifier`).
   No change to dependency direction; Domain (`Detection`, `Severity`) still has no
   FastAPI/SQLAlchemy/LangGraph/Anthropic/OpenAI/Discord SDK imports. No existing Incident
   table, port, or use case is modified except `Severity.parse()`'s internals (its public
   contract/signature is unchanged).
2. **Security impact** — Two new, deliberately-scoped raw-PII fields reach Discord
   (`userName`/`device`), explicitly authorized by the project owner (see Decision above) and
   implementable as a narrow, auditable allowlist. All other Detection free-text fields remain
   sanitized identically to Incidents. The generalized `Severity.parse()` preserves the existing
   fixed-allowlist, no-regex, no-`eval` security property. New cursor-integrity and volume-related
   operational risks are mitigated by fail-loud error handling and a hard per-run page cap.
3. **Data impact** — New tables `pending_detection_approvals`, `detection_collection_runs`
   (migration `007_add_detection_tables.py`). No change to any existing table's schema or data.
   `notification_deliveries` gains new rows keyed by Detection-derived idempotency hashes but no
   schema change.
4. **Operational impact** — New, more frequent (hourly vs. daily) scheduled job; new external-call
   volume against the same ESET host/credentials already in use (no new credential or network
   egress target). First run will be longer-running than a typical Incident run (skip-phase
   traversal of ~315 pages) — must not introduce a fixed Celery task timeout that would kill a
   legitimately long first run (confirm none exists before shipping). Cron interval and per-run
   limit defaults are engineering judgment calls flagged for post-launch tuning, not blocking.
5. **Required tests** — See acceptance-criteria.md, all items, especially 16-17 (the
   raw-vs-sanitized field split, the actual security-critical behavior of this task) and 7-11 (the
   cursor/backfill correctness behavior, the actual functional-correctness-critical behavior of
   this task).
6. **Approval** — Approved to proceed to implementation (codex). All decisions required before
   implementation per CLAUDE.md's "must not implement before [7 elements] are defined" — business
   requirement, data flow, trust boundary, failure scenarios, acceptance criteria, security
   requirements, test strategy — are defined across this document, task-spec.md, and
   acceptance-criteria.md. The one item that would have blocked (raw PII exposure policy) was
   already resolved by the project owner before this document was written.
