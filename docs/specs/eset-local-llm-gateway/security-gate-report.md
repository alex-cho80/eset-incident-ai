# Security Gate Report: Local LLM Gateway (Ollama)

Date: 2026-06-25
Role: codex (run directly against the working tree; implementation changes were already present)

## Tool Installation

The requested scanner binaries were not available in this environment. No files were modified to
install tools.

| Tool | Availability | Probe result |
|---|---|---|
| gitleaks | Unavailable | `which gitleaks` exit `1`; `gitleaks detect --source . --no-banner` exit `127` |
| semgrep | Unavailable | `which semgrep` exit `1`; `semgrep --config auto src/ tests/` exit `127` |
| trivy | Unavailable | `which trivy` exit `1`; `trivy fs .` / `trivy config .` exit `127` |

Additional lookup:

```bash
find /usr /opt /tmp -maxdepth 4 -type f \( -name gitleaks -o -name semgrep -o -name trivy \) 2>/dev/null
```

Result: no matching binaries found.

## Scanner Results

| Command | Exit code | Gate status | Findings |
|---|---:|---|---:|
| `gitleaks detect --source . --no-banner` | 127 | NOT RUN (tool unavailable) | N/A |
| `semgrep --config auto src/ tests/` | 127 | NOT RUN (tool unavailable) | N/A |
| `trivy fs .` | 127 | NOT RUN (tool unavailable) | N/A |
| `trivy config .` | 127 | NOT RUN (tool unavailable) | N/A |

Because no scanner command could execute, there are no scanner findings to classify as
pre-existing or newly introduced by this diff.

## Manual Security Checklist

### Secrets

PASS.

- No Ollama-related secret, credential, token, or password was introduced. The new Ollama settings
  are configuration only: `ollama_base_url`, `ollama_model`, and `ollama_keep_alive` in
  `src/eset_incident_ai/settings/config.py`; `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, and
  `OLLAMA_KEEP_ALIVE` in `.env.example`.
- No `sk-ant`-shaped Anthropic secret was found.
- `rg -n "ANTHROPIC_API_KEY|sk-ant" .` returned one historical documentation reference only:
  `docs/specs/llm-anthropic-gateway/acceptance-criteria.md:63`, which says no raw
  `ANTHROPIC_API_KEY` value should appear. It is not a credential value and is outside this diff.

### Personal Data Leakage

PASS.

`OllamaGateway.analyze()` sanitizes incident free text before prompt rendering:

- `src/eset_incident_ai/infrastructure/llm/ollama_gateway.py:79` sanitizes `incident.title`.
- `src/eset_incident_ai/infrastructure/llm/ollama_gateway.py:80` sanitizes `incident.summary`.
- `src/eset_incident_ai/infrastructure/llm/ollama_gateway.py:123-126` renders the prompt from the
  sanitized `title` and `summary`.

This matches the deleted `AnthropicGateway` behavior from `HEAD`.

### Unsafe Automation

PASS.

`OllamaGateway` does not execute commands from incident or evidence text. The gateway renders a
prompt, posts it to Ollama with `httpx`, parses the returned JSON through
`parse_incident_analysis()`, validates evidence IDs, and returns an advisory
`IncidentAnalysisResult`. No `subprocess`, `os.system`, `exec`, `eval`, shell invocation, endpoint
action, or remediation action exists in the gateway.

### Missing Approval Gates

PASS.

High/Critical human-approval routing is not bypassed or altered by this diff.

`git diff --stat -- src/eset_incident_ai/application/use_cases/collect_and_notify_incidents.py src/eset_incident_ai/application/use_cases/collect_and_notify_detections.py`

Result: no output.

The existing approval branches are still present:

- `collect_and_notify_incidents.py:77-83` saves High/Critical incidents for pending approval.
- `collect_and_notify_detections.py:118-125` saves High/Critical detections for pending approval
  and continues without auto-notification.

### Prompt Injection Handling

PASS.

`OllamaGateway` preserves the prompt-injection handling from the deleted `AnthropicGateway`:

- `src/eset_incident_ai/infrastructure/llm/ollama_gateway.py:81-83` calls
  `PromptInjectionFilter.contains_suspicious_instruction()` on the original incident title and
  summary.
- `src/eset_incident_ai/infrastructure/llm/ollama_gateway.py:114-117` appends the limitations
  notice when suspicious embedded instructions are detected.

## Overall Gate Status

BLOCKED for scanner completion because `gitleaks`, `semgrep`, and `trivy` are not available in this
environment, so the requested scanner finding counts cannot be produced here.

Manual security-gate checklist: PASS. No new manual finding was identified in the Ollama gateway
diff. No finding was available to classify as new versus pre-existing from the unavailable scanner
commands.
