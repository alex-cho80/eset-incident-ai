from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def intake_node(state: IncidentAgentState) -> IncidentAgentState:
    state.setdefault("retry_count", 0)
    state.setdefault("errors", [])
    return state
