# Contributing

Before implementation, read `CLAUDE.md`, `AGENTS.md`, `harness.yaml`, the relevant ADR, and any task specification.

## Development Rules

- Keep dependencies pointing inward: API / Infrastructure -> Application -> Domain.
- Add type annotations to new Python code.
- Validate external input with Pydantic.
- Use dependency injection instead of global mutable state.
- Keep HTTP timeouts and retry/error mapping on external calls.
- Add tests for new domain, security, and application behavior.

## Pull Request Evidence

Include changed components, security impact, migration impact, rollback method, test output, and known limitations.
