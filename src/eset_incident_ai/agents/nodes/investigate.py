from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def investigate_node(state: IncidentAgentState) -> IncidentAgentState:
    state["investigation"] = {"status": "pending_llm_gateway"}
    return state
