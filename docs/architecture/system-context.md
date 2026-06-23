# System Context

The system collects ESET incident data, stores raw and normalized records separately, indexes sanitized knowledge for retrieval, and produces evidence-grounded analysis recommendations.

External systems:

- ESET Connect API
- PostgreSQL with pgvector
- Redis
- External LLM provider
- Discord webhook
- Observability backend

The system is advisory by default. It does not execute endpoint actions.
