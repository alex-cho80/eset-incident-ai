from __future__ import annotations

from pydantic import BaseModel, Field


class PendingApprovalDTO(BaseModel):
    approval_id: int
    incident_id: str
    severity: str
    title: str
    status: str
    payload: dict[str, object] = Field(default_factory=dict)


class PendingDetectionApprovalDTO(BaseModel):
    approval_id: int
    detection_id: str
    severity: str
    title: str
    status: str
    payload: dict[str, object] = Field(default_factory=dict)
