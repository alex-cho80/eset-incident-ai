from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def security_review_node(state: IncidentAgentState) -> IncidentAgentState:
    state["security_review"] = {"passed": True}
    return state
