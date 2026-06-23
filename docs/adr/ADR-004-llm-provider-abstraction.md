# ADR-004: LLM Provider Abstraction

## Status

Accepted

## Decision

Expose LLM calls through an application port so Anthropic, OpenAI, or local providers can be swapped without changing domain logic.

## Consequences

Structured output validation and retry policy live at the gateway boundary.
