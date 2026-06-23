from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def approval_node(state: IncidentAgentState) -> IncidentAgentState:
    state.setdefault("approval_status", "pending")
    return state


def reject_node(state: IncidentAgentState) -> IncidentAgentState:
    state["approval_status"] = "rejected"
    return state
