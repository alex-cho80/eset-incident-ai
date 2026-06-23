from __future__ import annotations

from typing import Literal, TypedDict


class IncidentAgentState(TypedDict, total=False):
    workflow_run_id: str
    incident_id: str
    incident: dict[str, object]
    sanitized_incident: dict[str, object]
    risk_score: int
    severity: Literal["low", "medium", "high", "critical"]
    search_queries: list[str]
    retrieved_evidence: list[dict[str, object]]
    investigation: dict[str, object]
    root_cause: dict[str, object]
    remediation: dict[str, object]
    critique: dict[str, object]
    security_review: dict[str, object]
    confidence: float
    retry_count: int
    requires_human_approval: bool
    approval_status: Literal["not_required", "pending", "approved", "rejected"]
    notification_payload: dict[str, object]
    errors: list[str]
