from __future__ import annotations

from typing import Protocol

from eset_incident_ai.application.dto.approval_dto import PendingApprovalDTO


class ApprovalRepository(Protocol):
    async def save_pending(self, *, incident: dict[str, object], severity: str) -> None: ...

    async def list_pending(self, *, limit: int) -> list[PendingApprovalDTO]: ...

    async def get_pending(self, *, approval_id: int) -> PendingApprovalDTO | None: ...

    async def mark_reviewed(self, *, approval_id: int, status: str) -> None: ...
