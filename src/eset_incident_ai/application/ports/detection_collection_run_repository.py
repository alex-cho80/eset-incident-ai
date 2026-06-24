from __future__ import annotations

from typing import Protocol

from eset_incident_ai.application.dto.collection_result import DetectionCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import DetectionCollectionRunDTO


class DetectionCollectionRunRepository(Protocol):
    async def save_success(
        self,
        result: DetectionCollectionResult,
        *,
        last_page_token: str | None,
    ) -> None: ...

    async def save_cursor(self, *, last_page_token: str | None) -> None: ...

    async def save_failure(self, *, error_message: str) -> None: ...

    async def list_recent(self, *, limit: int) -> list[DetectionCollectionRunDTO]: ...

    async def latest(self) -> DetectionCollectionRunDTO | None: ...
