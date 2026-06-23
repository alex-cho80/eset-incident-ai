from __future__ import annotations

from typing import Protocol

from eset_incident_ai.application.dto.collection_result import IncidentCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import CollectionRunDTO


class CollectionRunRepository(Protocol):
    async def save_success(self, result: IncidentCollectionResult) -> None: ...

    async def save_failure(self, *, error_message: str) -> None: ...

    async def list_recent(self, *, limit: int) -> list[CollectionRunDTO]: ...

    async def latest(self) -> CollectionRunDTO | None: ...
