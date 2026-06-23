from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def remediation_node(state: IncidentAgentState) -> IncidentAgentState:
    state["remediation"] = {"status": "pending_llm_gateway"}
    return state
