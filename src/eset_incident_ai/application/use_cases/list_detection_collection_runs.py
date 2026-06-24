from __future__ import annotations

from eset_incident_ai.application.dto.collection_run_dto import DetectionCollectionRunDTO
from eset_incident_ai.application.ports.detection_collection_run_repository import (
    DetectionCollectionRunRepository,
)


class ListDetectionCollectionRuns:
    def __init__(self, collection_run_repository: DetectionCollectionRunRepository) -> None:
        self._collection_run_repository = collection_run_repository

    async def list_recent(self, *, limit: int = 20) -> list[DetectionCollectionRunDTO]:
        return await self._collection_run_repository.list_recent(limit=limit)

    async def latest(self) -> DetectionCollectionRunDTO | None:
        return await self._collection_run_repository.latest()
