from __future__ import annotations


class AssetLookupTool:
    async def lookup(self, asset_ref: str) -> dict[str, str]:
        return {"asset_ref": asset_ref, "status": "pending_asset_inventory"}
