from __future__ import annotations

from eset_incident_ai.agents.state import IncidentAgentState


def compose_notification_node(state: IncidentAgentState) -> IncidentAgentState:
    state.setdefault("notification_payload", {})
    return state


def notify_node(state: IncidentAgentState) -> IncidentAgentState:
    state["notification_payload"] = {
        **state.get("notification_payload", {}),
        "delivery_status": "pending_notifier",
    }
    return state
