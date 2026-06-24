from __future__ import annotations

import pytest

from eset_incident_ai.application.dto.approval_dto import PendingDetectionApprovalDTO
from eset_incident_ai.application.use_cases.list_pending_detection_approvals import (
    ListPendingDetectionApprovals,
)
from eset_incident_ai.application.use_cases.review_pending_detection_approval import (
    ReviewPendingDetectionApproval,
)
from eset_incident_ai.domain.exceptions import DomainError


class FakeDetectionApprovalRepository:
    def __init__(self, *, found: bool = True) -> None:
        self.found = found
        self.status: str | None = None

    async def save_pending(self, *, detection: dict[str, object], severity: str) -> None:
        _ = (detection, severity)

    async def list_pending(self, *, limit: int) -> list[PendingDetectionApprovalDTO]:
        return [
            PendingDetectionApprovalDTO(
                approval_id=1,
                detection_id=f"detection-{limit}",
                severity="high",
                title="Detection",
                status="pending",
                payload={"uuid": "detection-1"},
            )
        ]

    async def get_pending(self, *, approval_id: int) -> PendingDetectionApprovalDTO | None:
        if not self.found:
            return None
        return PendingDetectionApprovalDTO(
            approval_id=approval_id,
            detection_id="detection-1",
            severity="high",
            title="Detection",
            status="pending",
            payload={
                "uuid": "detection-1",
                "displayName": "Detection",
                "severityLevel": "SEVERITY_LEVEL_HIGH",
                "occurTime": "2026-06-24T00:00:00Z",
            },
        )

    async def mark_reviewed(self, *, approval_id: int, status: str) -> None:
        _ = approval_id
        self.status = status


class FakeDetectionNotificationBuilder:
    def severity(self, detection: dict[str, object]) -> object:
        return detection["severityLevel"]

    def build(
        self,
        detection: dict[str, object],
        analysis: object | None = None,
    ) -> dict[str, object]:
        _ = analysis
        return {"detection": detection}


class FakeNotificationRepository:
    def __init__(self, *, delivered: bool = False) -> None:
        self.delivered = delivered
        self.marked = False

    async def was_delivered(self, idempotency_key: str) -> bool:
        _ = idempotency_key
        return self.delivered

    async def mark_delivered(self, *, idempotency_key: str, destination: str) -> None:
        _ = (idempotency_key, destination)
        self.marked = True


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_list_pending_detection_approvals_use_case() -> None:
    result = await ListPendingDetectionApprovals(FakeDetectionApprovalRepository()).execute(limit=3)

    assert result[0].detection_id == "detection-3"


@pytest.mark.asyncio
async def test_review_pending_detection_approval_approves_and_notifies() -> None:
    approvals = FakeDetectionApprovalRepository()
    notifications = FakeNotificationRepository()
    notifier = FakeNotifier()
    use_case = ReviewPendingDetectionApproval(
        approval_repository=approvals,
        notification_builder=FakeDetectionNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=notifications,
        notifier=notifier,
    )

    result = await use_case.approve(approval_id=9)

    assert result.detection_id == "detection-1"
    assert result.notification_sent is True
    assert approvals.status == "approved"
    assert notifications.marked is True
    assert len(notifier.sent) == 1


@pytest.mark.asyncio
async def test_review_pending_detection_approval_rejects_without_notifying() -> None:
    approvals = FakeDetectionApprovalRepository()
    notifier = FakeNotifier()
    use_case = ReviewPendingDetectionApproval(
        approval_repository=approvals,
        notification_builder=FakeDetectionNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=FakeNotificationRepository(),
        notifier=notifier,
    )

    result = await use_case.reject(approval_id=8)

    assert result.status == "rejected"
    assert approvals.status == "rejected"
    assert notifier.sent == []


@pytest.mark.asyncio
async def test_review_pending_detection_approval_skips_duplicate_delivery() -> None:
    approvals = FakeDetectionApprovalRepository()
    use_case = ReviewPendingDetectionApproval(
        approval_repository=approvals,
        notification_builder=FakeDetectionNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=FakeNotificationRepository(delivered=True),
        notifier=FakeNotifier(),
    )

    result = await use_case.approve(approval_id=7)

    assert result.duplicate_skipped is True
    assert result.notification_sent is False
    assert approvals.status == "approved"


@pytest.mark.asyncio
async def test_review_pending_detection_approval_raises_when_missing() -> None:
    use_case = ReviewPendingDetectionApproval(
        approval_repository=FakeDetectionApprovalRepository(found=False),
        notification_builder=FakeDetectionNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=FakeNotificationRepository(),
        notifier=FakeNotifier(),
    )

    with pytest.raises(DomainError):
        await use_case.approve(approval_id=404)

    with pytest.raises(DomainError):
        await use_case.reject(approval_id=404)
