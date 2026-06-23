# ADR-002: Use LangGraph

## Status

Accepted

## Decision

Use LangGraph for bounded incident-analysis workflows with explicit routing through intake, retrieval, analysis, critique, security review, approval, and notification.

## Consequences

The workflow remains auditable and can enforce loop limits. Domain and application layers must not depend on LangGraph.
