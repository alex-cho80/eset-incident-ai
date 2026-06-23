from __future__ import annotations

from eset_incident_ai.domain.enums.severity import Severity


class RiskScoringService:
    _BASE = {
        Severity.LOW: 25,
        Severity.MEDIUM: 50,
        Severity.HIGH: 75,
        Severity.CRITICAL: 95,
    }

    def score(self, severity: Severity, *, detection_count: int = 0) -> int:
        return min(100, self._BASE[severity] + min(detection_count, 5) * 2)
