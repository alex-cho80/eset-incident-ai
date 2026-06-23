from __future__ import annotations

from typing import Any

from eset_incident_ai.application.dto.incident_dto import IncidentDTO
from eset_incident_ai.application.use_cases.normalize_incident import NormalizeIncident


class EsetIncidentMapper:
    def __init__(self, normalizer: NormalizeIncident) -> None:
        self._normalizer = normalizer

    def to_dto(self, payload: dict[str, Any]) -> IncidentDTO:
        return self._normalizer.execute(payload)
