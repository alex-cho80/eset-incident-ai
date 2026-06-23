from __future__ import annotations

from eset_incident_ai.domain.entities.incident import Incident


class SqlAlchemyIncidentRepository:
    async def upsert_incident(self, incident: Incident, *, content_hash: str) -> None:
        _ = (incident, content_hash)
        raise NotImplementedError("SQLAlchemy upsert wiring is pending")

    async def get_incident(self, incident_id: str) -> Incident | None:
        _ = incident_id
        raise NotImplementedError("SQLAlchemy query wiring is pending")
