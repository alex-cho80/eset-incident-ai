# Security Policy

## Secret Handling

Secrets must come from environment variables or a secret manager only. Do not commit ESET tokens, Discord webhook URLs, tenant identifiers, passwords, private IP inventories, or raw incident exports.

## Data Handling

Treat ESET API fields, retrieved knowledge documents, runbooks, and LLM output as untrusted input. Raw personal data must not be sent to external LLM providers or Discord unless an explicit policy permits it.

## Required Controls

- HMAC-based pseudonymization for identifiers.
- Evidence IDs for every material analysis claim.
- Human approval for high and critical incidents.
- Human approval for destructive recommendations.
- Idempotency keys for notifications and background writes.
- No raw prompts, credentials, tokens, or webhook URLs in logs.

## Reporting

Report suspected token exposure, prompt injection bypass, data leakage, or unsafe automation immediately. Rotate affected credentials before resuming processing.
