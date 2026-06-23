from __future__ import annotations

from eset_incident_ai.application.dto.approval_dto import PendingApprovalDTO
from eset_incident_ai.application.ports.approval_repository import ApprovalRepository


class ListPendingApprovals:
    def __init__(self, approval_repository: ApprovalRepository) -> None:
        self._approval_repository = approval_repository

    async def execute(self, *, limit: int = 50) -> list[PendingApprovalDTO]:
        return await self._approval_repository.list_pending(limit=limit)
