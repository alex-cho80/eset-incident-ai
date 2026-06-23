from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def route_after_critique(state: IncidentAgentState) -> str:
    critique = state.get("critique", {})
    unsupported = critique.get("unsupported_claim_count", 0)
    if isinstance(unsupported, int) and unsupported > 0:
        if state.get("retry_count", 0) < 2:
            return "retry_investigation"
        return "reject"
    if state.get("confidence", 0.0) < 0.65:
        return "reject"
    return "security_review"


def route_after_security_review(state: IncidentAgentState) -> str:
    review = state.get("security_review", {})
    if review.get("pass") is False:
        return "reject"
    if state.get("requires_human_approval", False):
        return "approval"
    return "compose"


def route_after_approval(state: IncidentAgentState) -> str:
    status = state.get("approval_status", "pending")
    if status == "approved":
        return "approved"
    if status == "rejected":
        return "rejected"
    return "pending"
