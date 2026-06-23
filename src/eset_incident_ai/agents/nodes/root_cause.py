from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def root_cause_node(state: IncidentAgentState) -> IncidentAgentState:
    state["root_cause"] = {"status": "pending_llm_gateway"}
    return state
