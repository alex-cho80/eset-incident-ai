from __future__ import annotations

import re

INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore (?:all )?(?:previous|prior) instructions"),
    re.compile(r"(?i)print (?:the )?(?:system prompt|secret|token|webhook)"),
    re.compile(r"(?i)send .*environment variables"),
    re.compile(r"(?i)curl .*metadata"),
]


class PromptInjectionFilter:
    def contains_suspicious_instruction(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in INJECTION_PATTERNS)
