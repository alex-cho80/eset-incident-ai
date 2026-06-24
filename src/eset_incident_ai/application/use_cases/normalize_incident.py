from __future__ import annotations

from typing import Any

from eset_incident_ai.application.dto.incident_dto import IncidentDTO
from eset_incident_ai.domain.enums.severity import Severity
from eset_incident_ai.security.sanitizer import Sanitizer


class NormalizeIncident:
    def __init__(self, sanitizer: Sanitizer) -> None:
        self._sanitizer = sanitizer

    def execute(self, payload: dict[str, Any]) -> IncidentDTO:
        title = str(payload.get("title") or payload.get("name") or "Untitled incident")
        sanitized_title = self._sanitizer.sanitize_text(title).text
        severity = Severity.parse(payload.get("severity"))
        return IncidentDTO(
            external_id=str(payload.get("uuid") or payload.get("id")),
            title=sanitized_title,
            severity=severity,
            summary=self._sanitizer.sanitize_text(str(payload.get("summary", ""))).text or None,
            normalized_payload={"source": "eset", "raw_keys": sorted(payload.keys())},
        )
