from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def parse(cls, value: object) -> Severity:
        text = str(value or "low").strip().lower()
        prefix = "incident_severity_level_"
        if text.startswith(prefix):
            text = text.removeprefix(prefix)
        if text in {"informational", "info", "unspecified"}:
            return cls.LOW
        if text in {severity.value for severity in cls}:
            return cls(text)
        return cls.LOW
