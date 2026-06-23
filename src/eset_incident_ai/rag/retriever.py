from __future__ import annotations

from eset_incident_ai.application.ports.vector_repository import VectorRepository
from eset_incident_ai.domain.entities.evidence import RetrievedEvidence


class Retriever:
    def __init__(self, vector_repository: VectorRepository) -> None:
        self._vector_repository = vector_repository

    async def retrieve(
        self, *, query: str, tenant_scope: str, limit: int = 10
    ) -> list[RetrievedEvidence]:
        return await self._vector_repository.search(
            query=query,
            tenant_scope=tenant_scope,
            limit=limit,
        )
