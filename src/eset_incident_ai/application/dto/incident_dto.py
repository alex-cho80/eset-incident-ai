from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from eset_incident_ai.domain.entities.incident import Incident
from eset_incident_ai.domain.enums.severity import Severity


class IncidentDTO(BaseModel):
    external_id: str
    title: str
    severity: Severity
    detected_at: datetime | None = None
    summary: str | None = None
    normalized_payload: dict[str, object] = Field(default_factory=dict)

    def to_domain(self) -> Incident:
        return Incident(
            id=self.external_id,
            external_id=self.external_id,
            title=self.title,
            severity=self.severity,
            detected_at=self.detected_at,
            summary=self.summary,
            normalized_payload=self.normalized_payload,
        )
