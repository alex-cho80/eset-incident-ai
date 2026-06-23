from __future__ import annotations

from typing import Protocol

from eset_incident_ai.domain.entities.incident import Incident


class IncidentRepository(Protocol):
    async def upsert_incident(self, incident: Incident, *, content_hash: str) -> None: ...

    async def get_incident(self, incident_id: str) -> Incident | None: ...
