# Data Flow

1. Collector retrieves ESET incidents with retry and timeout controls.
2. Raw payloads are stored in PostgreSQL JSONB with a payload hash.
3. Normalizer and sanitizer produce a safe incident representation.
4. RAG documents are chunked and embedded.
5. Retrieval returns scoped evidence IDs.
6. Agent analysis produces structured JSON.
7. Critic and security review evaluate claims and output safety.
8. Low-risk results may notify Discord; high-risk results wait for human approval.
