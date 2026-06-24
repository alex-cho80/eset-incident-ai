from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from eset_incident_ai.domain.enums.severity import Severity


@dataclass(frozen=True, slots=True)
class Detection:
    id: str
    external_id: str
    title: str
    severity: Severity
    category: str | None
    occurred_at: datetime | None
    summary: str | None
    object_name: str | None
    object_hash_sha1: str | None
    user_name: str | None
    device_name: str | None
    normalized_payload: dict[str, object]

    @property
    def requires_human_approval(self) -> bool:
        return self.severity in {Severity.HIGH, Severity.CRITICAL}
