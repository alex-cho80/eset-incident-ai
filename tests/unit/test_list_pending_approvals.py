from __future__ import annotations

import pytest

from eset_incident_ai.api.routes.approvals import (
    approve_pending_approval,
    pending_approvals,
    reject_pending_approval,
)
from eset_incident_ai.application.dto.approval_dto import PendingApprovalDTO
from eset_incident_ai.application.use_cases.list_pending_approvals import ListPendingApprovals
from eset_incident_ai.application.use_cases.review_pending_approval import ReviewPendingApproval
from eset_incident_ai.domain.exceptions import DomainError


class FakeApprovalRepository:
    def __init__(self, *, found: bool = True) -> None:
        self.found = found
        self.status: str | None = None

    async def save_pending(self, *, incident: dict[str, object], severity: str) -> None:
        _ = (incident, severity)

    async def list_pending(self, *, limit: int) -> list[PendingApprovalDTO]:
        return [
            PendingApprovalDTO(
                approval_id=1,
                incident_id=f"incident-{limit}",
                severity="high",
                title="Sanitized incident",
                status="pending",
                payload={"severity": "high"},
            )
        ]

    async def get_pending(self, *, approval_id: int) -> PendingApprovalDTO | None:
        if not self.found:
            return None
        return PendingApprovalDTO(
            approval_id=approval_id,
            incident_id="incident-1",
            severity="high",
            title="Sanitized incident",
            status="pending",
            payload={
                "uuid": "incident-1",
                "displayName": "Sanitized incident",
                "severity": "high",
                "updateTime": "2026-06-23T10:00:00Z",
            },
        )

    async def mark_reviewed(self, *, approval_id: int, status: str) -> None:
        _ = approval_id
        self.status = status


class FakeNotificationBuilder:
    def severity(self, incident: dict[str, object]) -> object:
        return incident["severity"]

    def build(self, incident: dict[str, object]) -> dict[str, object]:
        return {"incident": incident}


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
async def test_list_pending_approvals_use_case() -> None:
    result = await ListPendingApprovals(FakeApprovalRepository()).execute(limit=7)

    assert result[0].incident_id == "incident-7"


@pytest.mark.asyncio
async def test_pending_approvals_route_handler() -> None:
    result = await pending_approvals(
        use_case=ListPendingApprovals(FakeApprovalRepository()),
        limit=3,
    )

    assert result[0].approval_id == 1
    assert result[0].severity == "high"


@pytest.mark.asyncio
async def test_review_pending_approval_approves_and_notifies() -> None:
    approvals = FakeApprovalRepository()
    notifications = FakeNotificationRepository()
    notifier = FakeNotifier()
    use_case = ReviewPendingApproval(
        approval_repository=approvals,
        notification_builder=FakeNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=notifications,
        notifier=notifier,
    )

    result = await use_case.approve(approval_id=9)

    assert result.status == "approved"
    assert result.notification_sent is True
    assert approvals.status == "approved"
    assert notifications.marked is True
    assert len(notifier.sent) == 1


@pytest.mark.asyncio
async def test_review_pending_approval_rejects_without_notifying() -> None:
    approvals = FakeApprovalRepository()
    notifier = FakeNotifier()
    use_case = ReviewPendingApproval(
        approval_repository=approvals,
        notification_builder=FakeNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=FakeNotificationRepository(),
        notifier=notifier,
    )

    result = await reject_pending_approval(approval_id=8, use_case=use_case)

    assert result.status == "rejected"
    assert approvals.status == "rejected"
    assert notifier.sent == []


@pytest.mark.asyncio
async def test_approve_route_handler_skips_duplicate_delivery() -> None:
    approvals = FakeApprovalRepository()
    use_case = ReviewPendingApproval(
        approval_repository=approvals,
        notification_builder=FakeNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=FakeNotificationRepository(delivered=True),
        notifier=FakeNotifier(),
    )

    result = await approve_pending_approval(approval_id=7, use_case=use_case)

    assert result.status == "approved"
    assert result.duplicate_skipped is True
    assert result.notification_sent is False


@pytest.mark.asyncio
async def test_review_pending_approval_raises_when_missing() -> None:
    use_case = ReviewPendingApproval(
        approval_repository=FakeApprovalRepository(found=False),
        notification_builder=FakeNotificationBuilder(),  # type: ignore[arg-type]
        notification_repository=FakeNotificationRepository(),
        notifier=FakeNotifier(),
    )

    with pytest.raises(DomainError):
        await use_case.approve(approval_id=404)

    with pytest.raises(DomainError):
        await use_case.reject(approval_id=404)
