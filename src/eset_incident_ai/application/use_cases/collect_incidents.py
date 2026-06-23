from __future__ import annotations

from eset_incident_ai.application.ports.incident_source import IncidentSource


class CollectIncidents:
    def __init__(self, source: IncidentSource) -> None:
        self._source = source

    async def execute(
        self, *, updated_after: str | None, page_size: int
    ) -> list[dict[str, object]]:
        return [
            incident
            async for incident in self._source.iter_incidents(
                updated_after=updated_after,
                page_size=page_size,
            )
        ]
