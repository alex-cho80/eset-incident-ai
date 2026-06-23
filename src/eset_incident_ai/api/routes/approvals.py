from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from eset_incident_ai.api.dependencies import (
    get_list_pending_approvals,
    get_review_pending_approval,
)
from eset_incident_ai.application.dto.approval_dto import PendingApprovalDTO
from eset_incident_ai.application.dto.approval_result import ApprovalReviewResult
from eset_incident_ai.application.use_cases.list_pending_approvals import ListPendingApprovals
from eset_incident_ai.application.use_cases.review_pending_approval import ReviewPendingApproval

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/pending")
async def pending_approvals(
    use_case: Annotated[ListPendingApprovals, Depends(get_list_pending_approvals)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PendingApprovalDTO]:
    return await use_case.execute(limit=limit)


@router.post("/{approval_id}/approve")
async def approve_pending_approval(
    approval_id: int,
    use_case: Annotated[ReviewPendingApproval, Depends(get_review_pending_approval)],
) -> ApprovalReviewResult:
    return await use_case.approve(approval_id=approval_id)


@router.post("/{approval_id}/reject")
async def reject_pending_approval(
    approval_id: int,
    use_case: Annotated[ReviewPendingApproval, Depends(get_review_pending_approval)],
) -> ApprovalReviewResult:
    return await use_case.reject(approval_id=approval_id)
