from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from eset_incident_ai.api.dependencies import (
    get_collect_and_notify_detections,
    get_list_detection_collection_runs,
    get_list_pending_detection_approvals,
    get_review_pending_detection_approval,
    get_settings,
)
from eset_incident_ai.application.dto.approval_dto import PendingDetectionApprovalDTO
from eset_incident_ai.application.dto.approval_result import DetectionApprovalReviewResult
from eset_incident_ai.application.dto.collection_result import DetectionCollectionResult
from eset_incident_ai.application.dto.collection_run_dto import DetectionCollectionRunDTO
from eset_incident_ai.application.use_cases.collect_and_notify_detections import (
    CollectAndNotifyDetections,
)
from eset_incident_ai.application.use_cases.list_detection_collection_runs import (
    ListDetectionCollectionRuns,
)
from eset_incident_ai.application.use_cases.list_pending_detection_approvals import (
    ListPendingDetectionApprovals,
)
from eset_incident_ai.application.use_cases.review_pending_detection_approval import (
    ReviewPendingDetectionApproval,
)
from eset_incident_ai.settings.config import Settings

router = APIRouter(prefix="/detections", tags=["detections"])


class CollectDetectionsRequest(BaseModel):
    limit: int | None = Field(default=None, ge=1, le=10_000)


@router.post("/collect-and-notify")
async def collect_and_notify_detections(
    request: CollectDetectionsRequest,
    use_case: Annotated[
        CollectAndNotifyDetections,
        Depends(get_collect_and_notify_detections),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DetectionCollectionResult:
    return await use_case.execute(
        limit=request.limit or settings.detection_notify_limit,
        page_size=settings.eset_detection_page_size,
        max_pages_per_run=settings.detection_max_pages_per_run,
        backfill_window_days=settings.detection_backfill_window_days,
    )


@router.get("/collection-runs/latest")
async def latest_detection_collection_run(
    use_case: Annotated[
        ListDetectionCollectionRuns,
        Depends(get_list_detection_collection_runs),
    ],
) -> DetectionCollectionRunDTO | None:
    return await use_case.latest()


@router.get("/collection-runs")
async def list_detection_collection_runs(
    use_case: Annotated[
        ListDetectionCollectionRuns,
        Depends(get_list_detection_collection_runs),
    ],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[DetectionCollectionRunDTO]:
    return await use_case.list_recent(limit=limit)


@router.get("/pending-approvals")
async def pending_detection_approvals(
    use_case: Annotated[
        ListPendingDetectionApprovals,
        Depends(get_list_pending_detection_approvals),
    ],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PendingDetectionApprovalDTO]:
    return await use_case.execute(limit=limit)


@router.post("/pending-approvals/{approval_id}/approve")
async def approve_pending_detection_approval(
    approval_id: int,
    use_case: Annotated[
        ReviewPendingDetectionApproval,
        Depends(get_review_pending_detection_approval),
    ],
) -> DetectionApprovalReviewResult:
    return await use_case.approve(approval_id=approval_id)


@router.post("/pending-approvals/{approval_id}/reject")
async def reject_pending_detection_approval(
    approval_id: int,
    use_case: Annotated[
        ReviewPendingDetectionApproval,
        Depends(get_review_pending_detection_approval),
    ],
) -> DetectionApprovalReviewResult:
    return await use_case.reject(approval_id=approval_id)
