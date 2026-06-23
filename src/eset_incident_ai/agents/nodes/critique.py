from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def critique_node(state: IncidentAgentState) -> IncidentAgentState:
    state["critique"] = {"unsupported_claim_count": 0, "passed": True}
    state.setdefault("confidence", 0.0)
    return state
