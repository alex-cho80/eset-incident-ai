from __future__ import annotations

from enum import StrEnum


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    NOTIFIED = "notified"
    FAILED = "failed"
