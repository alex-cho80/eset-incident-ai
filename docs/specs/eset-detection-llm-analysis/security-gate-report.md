# Security Gate Report: LLM Analysis + Korean Output for Detection Notifications

Date: 2026-06-24
Role: claude (re-run directly against the working tree; codex's sandbox cannot resolve
`semgrep.dev`, same constraint documented in prior reports for this project)

## Tool Installation

Reused the same pre-installed tools under `/tmp/security-tools` from prior security-gate runs.

| Tool | Version | Install method |
|---|---:|---|
| gitleaks | 8.30.1 | Pre-installed under `/tmp/security-tools/bin/gitleaks` |
| semgrep | 1.167.0 | Pre-installed under `/tmp/security-tools/bin/semgrep`; run with `HOME=/tmp/security-tools/home` |
| trivy | 0.71.2 | Pre-installed under `/tmp/security-tools/bin/trivy`; run with `TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache` |

## Results

| Command | Exit code | Gate status | Findings |
|---|---:|---|---:|
| `gitleaks detect --no-banner` | 0 | PASS | 0 |
| `semgrep scan --config auto` | 0 | FAIL | 2 (pre-existing) |
| `trivy fs .` | 0 | PASS | 0 |
| `trivy config .` | 0 | FAIL | 2 (pre-existing) |

All four commands were run directly by claude against the full working tree (uncommitted changes
included), so any finding in any changed file would have surfaced here.

## Findings

### gitleaks detect --no-banner

No findings. `6 commits scanned, no leaks found.` No secret was introduced by this feature (no new
credential, API key, or webhook URL in any changed file — the analyzer wiring in
`dependencies.py` reuses the existing `settings.anthropic_api_key`/`settings.database_url`).

### semgrep scan --config auto

331 rules on 226 files, 2 blocking findings — the same two pre-existing findings already
documented in `eset-detections-ingestion/security-gate-report.md`:

| Severity | Rule | Location | Summary |
|---|---|---|---|
| Blocking | `python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected` | `scripts/smoke_check.py:30` | Dynamic value used with `urllib.urlopen`. |
| Blocking | `python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2` | `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py:96` | Direct Jinja2 `Environment` use flagged as possible XSS risk (plain-text LLM prompt rendering, not HTML). |

Neither finding touches any file changed by this feature. No new Semgrep finding was introduced —
in particular, no finding against `collect_and_notify_detections.py`'s new `json.dumps`/adapter
code or `detection_notification_builder.py`'s new `_analysis_fields`/`_safe_text` dict-handling
code, which were the files with the highest a-priori risk of flagging (untrusted-data
JSON-serialization, string interpolation into Discord payloads).

### trivy fs .

No findings. `uv.lock`: 0 vulnerabilities. No new dependency was added by this feature — the
analyzer wiring reuses `AnalyzeIncident`/`PgVectorRepository`/`AnthropicGateway`, all already
dependencies of the Incident pipeline.

### trivy config .

2 low-severity misconfiguration findings, same as prior reports:

| Severity | ID | Location | Summary |
|---|---|---|---|
| LOW | `DS-0026` | `deploy/docker/app.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |
| LOW | `DS-0026` | `deploy/docker/worker.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |

Pre-existing; this feature does not touch either Dockerfile.

## Overall Gate Status

FAIL — but on pre-existing, unrelated findings only, consistent with the precedent established in
`eset-detections-ingestion/security-gate-report.md` and `eset-severity-enum-fix/security-gate-report.md`.

`gitleaks detect --no-banner` and `trivy fs .` passed with no findings. `trivy config .` and
`semgrep scan --config auto` each reported the same findings already known and accepted as
pre-existing technical debt — none of which are touched by this feature.

No new finding of any kind was introduced by this feature, including in the security-sensitive
changed files (`collect_and_notify_detections.py`, `detection_notification_builder.py`,
`api/dependencies.py`). Approving this stage for the purpose of this change on that basis; the
pre-existing findings remain open as separate, already-tracked technical debt and are out of
scope for this feature.
