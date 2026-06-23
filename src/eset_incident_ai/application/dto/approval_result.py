from __future__ import annotations

from pydantic import BaseModel


class ApprovalReviewResult(BaseModel):
    approval_id: int
    incident_id: str
    status: str
    notification_sent: bool = False
    duplicate_skipped: bool = False
