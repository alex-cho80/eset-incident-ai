# ADR-001: Use PostgreSQL with pgvector

## Status

Accepted

## Decision

Use PostgreSQL for raw events, normalized incidents, workflow state, and vector-searchable knowledge chunks through pgvector.

## Consequences

This reduces operational complexity in the early phase and keeps metadata filters close to vector search. If retrieval scale exceeds PostgreSQL capacity, a separate vector database can be introduced behind the vector repository port.
