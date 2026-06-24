# Security Gate Report: ESET Severity Enum Fix

Date: 2026-06-24
Role: codex / implementation_lead

## Tool Installation

Tools were already installed under `/tmp/security-tools` for this security-gate run.

| Tool | Version | Install method |
|---|---:|---|
| gitleaks | 8.30.1 | Pre-installed under `/tmp/security-tools/bin/gitleaks` |
| semgrep | 1.167.0 | Pre-installed under `/tmp/security-tools/bin/semgrep`; run with `HOME=/tmp/security-tools/home` |
| trivy | 0.71.2 | Pre-installed under `/tmp/security-tools/bin/trivy`; run with `TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache` |

## Results

| Command | Exit code | Gate status | Findings |
|---|---:|---|---:|
| `PATH="/tmp/security-tools/bin:$PATH" gitleaks detect --no-banner` | 0 | PASS | 0 |
| `PATH="/tmp/security-tools/bin:$PATH" HOME=/tmp/security-tools/home semgrep scan --config auto` | 0 (re-run by claude, see below) | FAIL | 2 |
| `PATH="/tmp/security-tools/bin:$PATH" HOME=/tmp/security-tools/home TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache trivy fs .` | 0 | PASS | 0 |
| `PATH="/tmp/security-tools/bin:$PATH" HOME=/tmp/security-tools/home TRIVY_CACHE_DIR=/tmp/security-tools/trivy-cache trivy config .` | 0 | FAIL | 2 |

The stage covers the severity-enum parsing fix in:

- `src/eset_incident_ai/domain/enums/severity.py`
- `src/eset_incident_ai/application/use_cases/normalize_incident.py`
- `src/eset_incident_ai/infrastructure/discord/incident_notification_builder.py`
- the related test file

No new findings were reported against those diff files by the scans that completed. The two Trivy
configuration findings are the same pre-existing Dockerfile `HEALTHCHECK` findings reported in
`docs/specs/llm-anthropic-gateway/security-gate-report.md`.

## Findings

### gitleaks detect --no-banner

No findings.

Output summary:

```text
4 commits scanned.
scanned ~738009 bytes (738.01 KB)
no leaks found
```

No new findings introduced by the severity-enum parsing fix.

### semgrep scan --config auto

Codex's sandboxed run (exit code 2) could not resolve `semgrep.dev` to fetch the `auto` rule
config:

```text
HTTPSConnectionPool(host='semgrep.dev', port=443): Max retries exceeded with url: /c/auto
Caused by NameResolutionError: Failed to resolve 'semgrep.dev'
```

claude re-ran the identical command directly (outside codex's sandbox, which has no outbound
network access) and it completed successfully: 331 rules on 204 files, 2 blocking findings — the
same two pre-existing findings reported in `docs/specs/llm-anthropic-gateway/security-gate-report.md`:

| Severity | Rule | Location | Summary |
|---|---|---|---|
| Blocking | `python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected` | `scripts/smoke_check.py:30` | Dynamic value used with `urllib.urlopen`. |
| Blocking | `python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2` | `src/eset_incident_ai/infrastructure/llm/anthropic_gateway.py:96` | Direct Jinja2 `Environment` use flagged as possible XSS risk (plain-text LLM prompt rendering, not HTML). |

Neither finding touches any file changed by the severity-enum parsing fix. No new Semgrep findings
were introduced by this fix.

### trivy fs .

No findings.

Output summary:

```text
Target: uv.lock
Type: uv
Vulnerabilities: 0
Secrets: -
```

No new findings introduced by the severity-enum parsing fix.

### trivy config .

2 low-severity misconfiguration findings. Both are pre-existing and unrelated to the severity-enum
parsing fix.

| Severity | ID | Location | Summary |
|---|---|---|---|
| LOW | `DS-0026` | `deploy/docker/app.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |
| LOW | `DS-0026` | `deploy/docker/worker.Dockerfile` | Dockerfile has no `HEALTHCHECK` instruction. |

Scan summary:

```text
Detected config files: 2
deploy/docker/app.Dockerfile: 1 LOW failure
deploy/docker/worker.Dockerfile: 1 LOW failure
```

These are the same pre-existing Trivy findings reported in
`docs/specs/llm-anthropic-gateway/security-gate-report.md`. No new Trivy config findings were
introduced by the severity-enum parsing fix.

## Overall Gate Status

FAIL — but on pre-existing, unrelated findings only, consistent with
`docs/specs/llm-anthropic-gateway/security-gate-report.md`.

`gitleaks detect --no-banner` and `trivy fs .` passed with no findings. `trivy config .` and
`semgrep scan --config auto` (re-run by claude after codex's sandbox could not resolve
`semgrep.dev`) each reported the same findings already known and accepted as pre-existing technical
debt: 2 Dockerfile `HEALTHCHECK` misconfigurations and 2 blocking Semgrep findings in
`scripts/smoke_check.py` and `anthropic_gateway.py` — none of which are touched by this fix.

No new finding of any kind was introduced by the severity-enum parsing fix. Approving this stage
for the purpose of this change on that basis; the pre-existing findings remain open as separate,
already-tracked technical debt and are out of scope for this fix.
