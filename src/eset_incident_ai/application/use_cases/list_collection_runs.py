from __future__ import annotations

from eset_incident_ai.application.dto.collection_run_dto import CollectionRunDTO
from eset_incident_ai.application.ports.collection_run_repository import (
    CollectionRunRepository,
)


class ListCollectionRuns:
    def __init__(self, collection_run_repository: CollectionRunRepository) -> None:
        self._collection_run_repository = collection_run_repository

    async def list_recent(self, *, limit: int = 20) -> list[CollectionRunDTO]:
        return await self._collection_run_repository.list_recent(limit=limit)

    async def latest(self) -> CollectionRunDTO | None:
        return await self._collection_run_repository.latest()
