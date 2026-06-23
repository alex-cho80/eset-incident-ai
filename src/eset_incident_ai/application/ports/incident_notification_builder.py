from __future__ import annotations

from typing import Any, Protocol

from eset_incident_ai.domain.entities.analysis import IncidentAnalysisResult
from eset_incident_ai.domain.enums.severity import Severity


class IncidentNotificationBuilder(Protocol):
    def severity(self, incident: dict[str, Any]) -> Severity: ...

    def build(
        self,
        incident: dict[str, Any],
        analysis: IncidentAnalysisResult | None = None,
    ) -> dict[str, Any]: ...
