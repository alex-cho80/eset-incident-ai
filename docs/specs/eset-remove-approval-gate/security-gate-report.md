# Security Gate Report: Remove human-approval gate for HIGH/CRITICAL

Scanners unavailable in this environment (gitleaks/semgrep/trivy not installed — known
pre-existing limitation, see [[project-eset-incident-ai]]). Manual checklist + bandit used instead.

- **Secrets**: `bandit -r scripts/backfill_pending_detection_approvals.py` — no issues. Manual
  grep for webhook/token/secret/password confirms only env-var *names* appear in code/error
  messages, never literal values; all secrets loaded via `Settings()` at runtime.
- **Personal data leakage**: No new PII surface — same `Sanitizer.sanitize_text` / raw
  IP-hostname-userName policy as the existing live path, applied identically regardless of
  severity (this change doesn't add or remove any sanitization call).
- **Unsafe automation**: Backfill script is a manual one-off (`python -m
  scripts.backfill_pending_detection_approvals`), not wired into `bootstrap.py`, celery beat, or
  any cron — confirmed by grep, no references to it outside the script and its test.
- **Missing approval gates**: This is the deliberate subject of the change (explicit user decision
  2026-06-25, with the CLAUDE.md conflict surfaced and acknowledged before confirming via
  AskUserQuestion) — not an accidental regression. CLAUDE.md text updated in the same diff.
- **Prompt injection handling**: Unchanged — `AnalyzeIncident`/`OllamaGateway` already treat
  incident/detection text as untrusted (existing `PromptInjectionFilter`), and this diff doesn't
  touch that path; HIGH/CRITICAL now reaches the same already-hardened analysis call LOW/MEDIUM
  uses, not a new or weaker one.

**Result: PASS (manual checklist + bandit; full scanner suite still blocked by environment, not by
this diff).**
