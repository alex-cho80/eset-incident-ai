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
        text = text.split("_level_")[-1]
        if text in {"informational", "info", "unspecified"}:
            return cls.LOW
        if text in {severity.value for severity in cls}:
            return cls(text)
        return cls.LOW

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    def meets_threshold(self, minimum: Severity) -> bool:
        return self.rank >= minimum.rank


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}
