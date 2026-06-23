from __future__ import annotations


class IndexIncident:
    async def execute(self, *, incident_id: str) -> str:
        return incident_id
