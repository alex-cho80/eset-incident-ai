from __future__ import annotations

from eset_incident_ai.application.dto.approval_dto import PendingDetectionApprovalDTO
from eset_incident_ai.application.ports.detection_approval_repository import (
    DetectionApprovalRepository,
)


class ListPendingDetectionApprovals:
    def __init__(self, approval_repository: DetectionApprovalRepository) -> None:
        self._approval_repository = approval_repository

    async def execute(self, *, limit: int = 50) -> list[PendingDetectionApprovalDTO]:
        return await self._approval_repository.list_pending(limit=limit)
