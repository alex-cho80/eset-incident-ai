from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
_IPV4_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
# Runs after PRIVATE_IP_RE has already replaced RFC1918 ranges with pseudonyms, so any
# remaining dotted-quad match here is a public address.
PUBLIC_IP_RE = re.compile(rf"\b(?:{_IPV4_OCTET}\.){{3}}{_IPV4_OCTET}\b")
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\")
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

        def replace_private_ip(match: re.Match[str]) -> str:
            original = match.group(0)
            masked = replacements.setdefault(original, self.pseudonym("PRIVATE_IP", original))
            return masked

        def replace_public_ip(match: re.Match[str]) -> str:
            original = match.group(0)
            masked = replacements.setdefault(original, self.pseudonym("PUBLIC_IP", original))
            return masked

        sanitized = EMAIL_RE.sub(replace_email, text)
        sanitized = PRIVATE_IP_RE.sub(replace_private_ip, sanitized)
        sanitized = PUBLIC_IP_RE.sub(replace_public_ip, sanitized)
        sanitized = WINDOWS_PATH_RE.sub(r"<USER_HOME>\\", sanitized)
        sanitized = TOKEN_RE.sub("<SECRET_REDACTED>", sanitized)
        return SanitizationResult(text=sanitized, replacements=replacements)
