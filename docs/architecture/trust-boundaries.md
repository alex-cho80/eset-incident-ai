# Trust Boundaries

Untrusted inputs:

- ESET incident fields
- Knowledge documents
- Runbooks
- LLM responses
- API request payloads

Protected boundaries:

- Secrets are environment or secret-manager only.
- Raw ESET data stays inside persistence.
- LLM receives sanitized incident data and retrieved excerpts only.
- Discord receives policy-approved summaries only.
