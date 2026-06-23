from __future__ import annotations


class RunbookSearchTool:
    async def search(self, query: str) -> list[dict[str, str]]:
        return [{"query": query, "status": "pending_retriever"}]
