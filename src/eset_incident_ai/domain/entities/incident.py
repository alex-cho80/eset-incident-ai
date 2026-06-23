from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from eset_incident_ai.domain.entities.detection import Detection
from eset_incident_ai.domain.enums.severity import Severity


@dataclass(frozen=True, slots=True)
class Incident:
    id: str
    external_id: str
    title: str
    severity: Severity
    detected_at: datetime | None
    summary: str | None
    normalized_payload: dict[str, object]
    detections: tuple[Detection, ...] = field(default_factory=tuple)

    @property
    def requires_human_approval(self) -> bool:
        return self.severity in {Severity.HIGH, Severity.CRITICAL}
