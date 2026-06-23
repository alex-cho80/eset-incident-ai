# Threat Model

Primary risks:

- Secret exposure through logs, prompts, or Discord.
- Prompt injection embedded in incident fields or runbooks.
- Cross-tenant retrieval leakage.
- Unsupported LLM claims presented as facts.
- Unsafe recommendations without approval.

Required mitigations:

- Sanitization and secret detection before external transmission.
- Evidence IDs for factual claims.
- Tenant and access metadata filters for retrieval.
- Human approval for high/critical incidents and destructive actions.
- Deterministic CI and security gates before deployment.
