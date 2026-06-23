from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def retrieve_node(state: IncidentAgentState) -> IncidentAgentState:
    state.setdefault("retrieved_evidence", [])
    return state
