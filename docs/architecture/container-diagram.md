# Container Diagram

```text
ESET API -> FastAPI/Celery Collector -> PostgreSQL
                               |       -> Redis Queue
                               |       -> pgvector Retrieval
                               |       -> LLM Gateway
                               |       -> Discord Webhook
                               v
                         OpenTelemetry
```
