from __future__ import annotations


class MitreLookupTool:
    async def lookup(self, technique_id: str) -> dict[str, str]:
        return {"technique_id": technique_id, "status": "pending_mitre_dataset"}
