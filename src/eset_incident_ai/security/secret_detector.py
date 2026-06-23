from __future__ import annotations

import re
from dataclasses import dataclass

SECRET_PATTERNS = {
    "discord_webhook": re.compile(r"https://discord(?:app)?\.com/api/webhooks/\S+"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{20,}"),
    "generic_secret": re.compile(r"(?i)\b(?:api[_-]?key|client[_-]?secret|password)\s*[:=]\s*\S+"),
}


@dataclass(frozen=True, slots=True)
class SecretFinding:
    kind: str
    start: int
    end: int


class SecretDetector:
    def find(self, text: str) -> list[SecretFinding]:
        findings: list[SecretFinding] = []
        for kind, pattern in SECRET_PATTERNS.items():
            findings.extend(
                SecretFinding(kind=kind, start=m.start(), end=m.end())
                for m in pattern.finditer(text)
            )
        return sorted(findings, key=lambda finding: finding.start)
