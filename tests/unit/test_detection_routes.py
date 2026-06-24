from __future__ import annotations

from datetime import UTC, datetime

import pytest

from eset_incident_ai.api.routes.detections import (
    CollectDetectionsRequest,
    approve_pending_detection_approval,
    collect_and_notify_detections,
    latest_detection_collection_run,
    list_detection_collection_runs,
    pending_detection_approvals,
    reject_pending_detection_approval,
)
from eset_incident_ai.application.dto.approval_dto import PendingDetectionApprovalDTO
from eset_incident_ai.application.dto.approval_result import DetectionApprovalReviewResult
from eset_incident_ai.application.dto.collection_result import DetectionCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import DetectionCollectionRunDTO
from eset_incident_ai.settings.config import Settings


class FakeCollectDetections:
    async def execute(
        self,
        *,
        limit: int,
        page_size: int,
        max_pages_per_run: int,
        backfill_window_days: int,
    ) -> DetectionCollectionResult:
        return DetectionCollectionResult(
            collected_count=page_size,
            notified_count=limit,
            skipped_count=max_pages_per_run,
            observed_keys=[str(backfill_window_days)],
        )


class FakeListRuns:
    async def latest(self) -> DetectionCollectionRunDTO:
        return DetectionCollectionRunDTO(
            run_id=1,
            status="succeeded",
            collected_count=1,
            notified_count=1,
            duplicate_skipped_count=0,
            pending_approval_count=0,
            skipped_count=0,
            observed_keys=["uuid"],
            last_page_token="page-2",  # noqa: S106
            created_at=datetime.now(UTC),
        )

    async def list_recent(self, *, limit: int) -> list[DetectionCollectionRunDTO]:
        latest = await self.latest()
        latest.run_id = limit
        return [latest]


class FakeListApprovals:
    async def execute(self, *, limit: int) -> list[PendingDetectionApprovalDTO]:
        return [
            PendingDetectionApprovalDTO(
                approval_id=1,
                detection_id=f"detection-{limit}",
                severity="high",
                title="Detection",
                status="pending",
                payload={"uuid": "detection"},
            )
        ]


class FakeReviewApproval:
    async def approve(self, *, approval_id: int) -> DetectionApprovalReviewResult:
        return DetectionApprovalReviewResult(
            approval_id=approval_id,
            detection_id="detection-1",
            status="approved",
            notification_sent=True,
        )

    async def reject(self, *, approval_id: int) -> DetectionApprovalReviewResult:
        return DetectionApprovalReviewResult(
            approval_id=approval_id,
            detection_id="detection-1",
            status="rejected",
        )


@pytest.mark.asyncio
async def test_collect_and_notify_detections_route_uses_settings_defaults() -> None:
    result = await collect_and_notify_detections(
        request=CollectDetectionsRequest(),
        use_case=FakeCollectDetections(),  # type: ignore[arg-type]
        settings=Settings(
            sanitizer_hmac_secret="test-secret",  # noqa: S106
            detection_notify_limit=7,
            eset_detection_page_size=999,
            detection_max_pages_per_run=11,
            detection_backfill_window_days=22,
        ),
    )

    assert result.notified_count == 7
    assert result.collected_count == 999
    assert result.skipped_count == 11
    assert result.observed_keys == ["22"]


@pytest.mark.asyncio
async def test_detection_collection_routes() -> None:
    latest = await latest_detection_collection_run(use_case=FakeListRuns())  # type: ignore[arg-type]
    runs = await list_detection_collection_runs(use_case=FakeListRuns(), limit=3)  # type: ignore[arg-type]

    assert latest is not None
    assert latest.last_page_token == "page-2"  # noqa: S105
    assert runs[0].run_id == 3


@pytest.mark.asyncio
async def test_detection_approval_routes() -> None:
    pending = await pending_detection_approvals(
        use_case=FakeListApprovals(),  # type: ignore[arg-type]
        limit=4,
    )
    approved = await approve_pending_detection_approval(
        approval_id=7,
        use_case=FakeReviewApproval(),  # type: ignore[arg-type]
    )
    rejected = await reject_pending_detection_approval(
        approval_id=8,
        use_case=FakeReviewApproval(),  # type: ignore[arg-type]
    )

    assert pending[0].detection_id == "detection-4"
    assert approved.notification_sent is True
    assert rejected.status == "rejected"
