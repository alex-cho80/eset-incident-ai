from __future__ import annotations


class IncidentLookupTool:
    async def lookup(self, incident_id: str) -> dict[str, str]:
        return {"incident_id": incident_id, "status": "pending_repository"}
