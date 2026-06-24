from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\")
WINDOWS_LEGACY_HOME_RE = re.compile(r"[A-Za-z]:\\Documents and Settings\\[^\\\s]+\\")
UNIX_HOME_RE = re.compile(r"/home/[^/\s]+/")
ACCOUNT_WORD_RE = r"[A-Za-z0-9][A-Za-z0-9._-]*"
ACCOUNT_TWO_WORD_RE = rf"(?>{ACCOUNT_WORD_RE} {ACCOUNT_WORD_RE})"
DOMAIN_ACCOUNT_RE = re.compile(
    rf"(?<!\\)\b(?:{ACCOUNT_TWO_WORD_RE}\\{ACCOUNT_TWO_WORD_RE}|"
    rf"{ACCOUNT_TWO_WORD_RE}\\{ACCOUNT_WORD_RE}|{ACCOUNT_WORD_RE}\\{ACCOUNT_WORD_RE})"
    r"\b(?![A-Za-z0-9 ._-]*\\)"
)
TOKEN_RE = re.compile(r"(?i)\b(?:token|secret|password|webhook)[=:]\s*['\"]?[^'\"\s]+")


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    text: str
    replacements: dict[str, str]


class Sanitizer:
    def __init__(self, hmac_secret: str) -> None:
        if not hmac_secret:
            raise ValueError("hmac_secret is required")
        self._secret = hmac_secret.encode("utf-8")

    def pseudonym(self, label: str, value: str) -> str:
        digest = hmac.new(self._secret, value.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{label}_{digest[:8].upper()}"

    def sanitize_text(self, text: str) -> SanitizationResult:
        replacements: dict[str, str] = {}

        def replace_email(match: re.Match[str]) -> str:
            original = match.group(0)
            masked = replacements.setdefault(original, self.pseudonym("EMAIL", original))
            return masked

        def replace_account(match: re.Match[str]) -> str:
            original = match.group(0)
            masked = replacements.setdefault(original, self.pseudonym("ACCOUNT", original))
            return masked

        sanitized = EMAIL_RE.sub(replace_email, text)
        sanitized = WINDOWS_PATH_RE.sub(r"<USER_HOME>\\", sanitized)
        sanitized = WINDOWS_LEGACY_HOME_RE.sub(r"<USER_HOME>\\", sanitized)
        sanitized = UNIX_HOME_RE.sub("<USER_HOME>/", sanitized)
        sanitized = DOMAIN_ACCOUNT_RE.sub(replace_account, sanitized)
        sanitized = TOKEN_RE.sub("<SECRET_REDACTED>", sanitized)
        return SanitizationResult(text=sanitized, replacements=replacements)
