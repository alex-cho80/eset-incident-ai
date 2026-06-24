# Security Gate Report: ESET Detections Ingestion

Date: 2026-06-24
Role: claude (re-run directly; codex's sandbox cannot resolve `semgrep.dev`, same constraint as
documented in `eset-severity-enum-fix/security-gate-report.md`)

## Tool Installation

Reused the same pre-installed tools under `/tmp/security-tools` from the prior security-gate run.

| Tool | Version | Install method |
|---|---:|---|
| gitleaks | 8.30.1 | Pre-installed under `/tmp/security-tools/bin/gitleaks` |
| semgrep | 1.167.0 | Pre-installed under `/tmp/security-tools/bin/semgrep`; run with `HOME=/tmp/security-tools/home` |
| trivy | 0.71.2 | Pre-installed under `/tmp/security-tools/bin/trivy`; run with `TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache` |

## Results

| Command | Exit code | Gate status | Findings |
|---|---:|---|---:|
| `PATH="/tmp/security-tools/bin:$PATH" gitleaks detect --no-banner` | 0 | PASS | 0 |
| `PATH="/tmp/security-tools/bin:$PATH" HOME=/tmp/security-tools/home semgrep scan --config auto` | 0 | FAIL | 2 |
| `PATH="/tmp/security-tools/bin:$PATH" TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache trivy fs .` | 0 | PASS | 0 |
| `PATH="/tmp/security-tools/bin:$PATH" TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache trivy config .` | 0 | FAIL | 2 |

All four commands were run directly by claude against the full working tree (not scoped to a diff
filter), so any finding in any file would have surfaced here.

## Findings

### gitleaks detect --no-banner

No findings.

```text
5 commits scanned.
scanned ~757147 bytes (757.15 KB)
no leaks found
```

No secret was introduced by this feature (no new ESET/Discord credential, no hardcoded token in
the new client/repository/settings code).

### semgrep scan --config auto

331 rules on 222 files, 2 blocking findings — the same two pre-existing findings already documented
in `eset-severity-enum-fix/security-gate-report.md` and `llm-anthropic-gateway/security-gate-report.md`:

| Severity | Rule | Location | Summary |
|---|---|---|---|
| Blocking | `python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected` | `scripts/smoke_check.py:30` | Dynamic value used with `urllib.urlopen`. |
| Blocking | `python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2` | `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py:96` | Direct Jinja2 `Environment` use flagged as possible XSS risk (plain-text LLM prompt rendering, not HTML). |

Neither finding touches any file created or modified by the Detections ingestion feature. No new
Semgrep findings were introduced — in particular, no finding against
`infrastructure/discord/detection_notification_builder.py`,
`infrastructure/persistence/detection_approval_repository.py`, or
`infrastructure/eset/detection_client.py`, which were the files with the highest a-priori risk of
flagging (raw-string handling, SQL construction, HTTP calls).

### trivy fs .

No findings.

```text
Target: uv.lock
Type: uv
Vulnerabilities: 0
Secrets: -
```

No new dependency was added by this feature (`tenacity`, `httpx`, `psycopg` were already
dependencies, reused as-is by `EsetDetectionClient`/`PostgresDetectionApprovalRepository`).

### trivy config .

2 low-severity misconfiguration findings, same as the prior reports.

| Severity | ID | Location | Summary |
|---|---|---|---|
| LOW | `DS-0026` | `deploy/docker/app.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |
| LOW | `DS-0026` | `deploy/docker/worker.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |

Pre-existing; this feature does not touch either Dockerfile.

## Overall Gate Status

FAIL — but on pre-existing, unrelated findings only, consistent with the precedent already
established in `eset-severity-enum-fix/security-gate-report.md`.

`gitleaks detect --no-banner` and `trivy fs .` passed with no findings. `trivy config .` and
`semgrep scan --config auto` each reported the same findings already known and accepted as
pre-existing technical debt: 2 Dockerfile `HEALTHCHECK` misconfigurations and 2 blocking Semgrep
findings in `scripts/smoke_check.py` and `anthropic_gateway.py` — none of which are touched by the
Detections ingestion feature.

No new finding of any kind was introduced by this feature, including in the security-sensitive new
files (`detection_notification_builder.py`, `detection_approval_repository.py`,
`detection_client.py`). Approving this stage for the purpose of this change on that basis; the
pre-existing findings remain open as separate, already-tracked technical debt and are out of scope
for this feature.
