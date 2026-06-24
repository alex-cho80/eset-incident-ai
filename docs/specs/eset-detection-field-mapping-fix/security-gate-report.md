# Security Gate Report: Detection Field Mapping + Sanitizer Coverage Fix

Date: 2026-06-24
Role: claude (re-run directly against the working tree; codex's sandbox cannot resolve
`semgrep.dev`/`pypi.org`, same constraint documented in prior reports for this project)

## Tool Installation

Reused the same pre-installed tools under `/tmp/security-tools` from prior security-gate runs.

| Tool | Version | Install method |
|---|---:|---|
| gitleaks | 8.30.1 | Pre-installed under `/tmp/security-tools/bin/gitleaks` |
| semgrep | 1.167.0 | Pre-installed under `/tmp/security-tools/bin/semgrep`; run with `HOME=/tmp/security-tools/home` |
| trivy | 0.71.2 | Pre-installed under `/tmp/security-tools/bin/trivy`; run with `TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache` |

## Results

| Command | Findings | Gate status |
|---|---:|---|
| `gitleaks detect --no-banner` | 0 | PASS |
| `semgrep scan --config auto` | 2 (pre-existing) | FAIL |
| `trivy fs .` | 0 | PASS |
| `trivy config .` | 2 (pre-existing) | FAIL |

All four commands were run directly by claude against the full working tree (uncommitted changes
included), so any finding in any changed file would have surfaced here.

## Findings

### gitleaks detect --no-banner

No findings. `7 commits scanned, no leaks found.` No secret introduced — the `Sanitizer` change
reuses the existing constructor-injected HMAC secret; no new credential anywhere in the diff.

### semgrep scan --config auto

331 rules on 230 files, 2 blocking findings — the same two pre-existing findings already documented
in `eset-detection-llm-analysis/security-gate-report.md` and prior reports:

| Severity | Rule | Location | Summary |
|---|---|---|---|
| Blocking | `python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected` | `scripts/smoke_check.py:30` | Dynamic value used with `urllib.urlopen`. |
| Blocking | `python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2` | `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py:96` | Direct Jinja2 `Environment` use flagged as possible XSS risk (plain-text LLM prompt rendering, not HTML). |

Neither finding touches any file changed by this fix. No new finding against `sanitizer.py`,
`detection_notification_builder.py`, or `detection_approval_repository.py` — notable because the new
regex-based redaction logic and JSON-serialization fix were the highest a-priori risk surface for a
new finding (e.g. a ReDoS-flagged pattern), and none was raised.

### trivy fs .

No findings. `uv.lock`: 0 vulnerabilities. No new dependency added by this fix.

### trivy config .

2 low-severity misconfiguration findings, identical to all prior reports for this project:

| Severity | ID | Location | Summary |
|---|---|---|---|
| LOW | `DS-0026` | `deploy/docker/app.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |
| LOW | `DS-0026` | `deploy/docker/worker.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |

Pre-existing; this fix does not touch either Dockerfile.

## Overall Gate Status

FAIL — but on pre-existing, unrelated findings only, consistent with the precedent established in
every prior security-gate report for this project. `gitleaks detect --no-banner` and `trivy fs .`
passed with zero findings. `trivy config .` and `semgrep scan --config auto` each reported only the
same already-known, already-accepted findings, none of which are touched by this fix.

No new finding of any kind was introduced by this fix, including in the three changed source files
with the highest a-priori risk (`sanitizer.py`'s new regex patterns, `detection_notification_builder.py`
and `detection_approval_repository.py`'s new untrusted-`context`-dict traversal). Approving this
stage for the purpose of this change on that basis; the pre-existing findings remain open as
separate, already-tracked technical debt and are out of scope for this fix.
