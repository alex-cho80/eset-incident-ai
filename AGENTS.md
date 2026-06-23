# Codex Engineering Contract

## Before coding

Read:

1. CLAUDE.md
2. harness.yaml
3. Relevant ADR
4. Task specification
5. Existing tests

Do not infer missing requirements silently.

## Implementation rules

- Python 3.12+
- Full type annotations are required.
- Use Pydantic for external input validation.
- Use dependency injection.
- No global mutable state.
- No hardcoded credentials, URLs or tenant identifiers.
- All HTTP calls require timeout, retry and error mapping.
- All database writes must be idempotent where applicable.
- Every background task must support retry without duplicate processing.
- Do not log tokens, prompts containing secrets, or raw personal data.

## Required verification

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=src --cov-fail-under=85
uv run bandit -r src
uv run pip-audit