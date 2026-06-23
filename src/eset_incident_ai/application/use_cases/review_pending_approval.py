from __future__ import annotations

from eset_incident_ai.application.dto.approval_result import ApprovalReviewResult
from eset_incident_ai.application.ports.approval_repository import ApprovalRepository
from eset_incident_ai.application.ports.incident_notification_builder import (
    IncidentNotificationBuilder,
)
from eset_incident_ai.application.ports.notification_repository import NotificationRepository
from eset_incident_ai.application.ports.notifier import Notifier
from eset_incident_ai.domain.exceptions import DomainError
from eset_incident_ai.infrastructure.discord.message_builder import build_idempotency_key


class ReviewPendingApproval:
    def __init__(
        self,
        *,
        approval_repository: ApprovalRepository,
        notification_builder: IncidentNotificationBuilder,
        notification_repository: NotificationRepository,
        notifier: Notifier,
        destination: str = "discord",
    ) -> None:
        self._approval_repository = approval_repository
        self._notification_builder = notification_builder
        self._notification_repository = notification_repository
        self._notifier = notifier
        self._destination = destination

    async def approve(self, *, approval_id: int) -> ApprovalReviewResult:
        approval = await self._approval_repository.get_pending(approval_id=approval_id)
        if approval is None:
            raise DomainError("Pending approval was not found.")

        idempotency_key = self._idempotency_key(approval.payload)
        if await self._notification_repository.was_delivered(idempotency_key):
            await self._approval_repository.mark_reviewed(
                approval_id=approval_id,
                status="approved",
            )
            return ApprovalReviewResult(
                approval_id=approval.approval_id,
                incident_id=approval.incident_id,
                status="approved",
                duplicate_skipped=True,
            )

        await self._notifier.send(self._notification_builder.build(approval.payload))
        await self._notification_repository.mark_delivered(
            idempotency_key=idempotency_key,
            destination=self._destination,
        )
        await self._approval_repository.mark_reviewed(
            approval_id=approval_id,
            status="approved",
        )
        return ApprovalReviewResult(
            approval_id=approval.approval_id,
            incident_id=approval.incident_id,
            status="approved",
            notification_sent=True,
        )

    async def reject(self, *, approval_id: int) -> ApprovalReviewResult:
        approval = await self._approval_repository.get_pending(approval_id=approval_id)
        if approval is None:
            raise DomainError("Pending approval was not found.")

        await self._approval_repository.mark_reviewed(
            approval_id=approval_id,
            status="rejected",
        )
        return ApprovalReviewResult(
            approval_id=approval.approval_id,
            incident_id=approval.incident_id,
            status="rejected",
        )

    def _idempotency_key(self, incident: dict[str, object]) -> str:
        incident_id = str(incident.get("uuid") or incident.get("displayName") or "unknown")
        analysis_version = str(
            incident.get("updateTime") or incident.get("createTime") or "unknown"
        )
        return build_idempotency_key(incident_id, analysis_version, self._destination)
