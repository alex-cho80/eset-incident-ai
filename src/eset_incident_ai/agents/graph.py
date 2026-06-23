from __future__ import annotations

from typing import Any


def build_incident_graph() -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        return None

    from eset_incident_ai.agents.nodes.approval import approval_node, reject_node
    from eset_incident_ai.agents.nodes.critique import critique_node
    from eset_incident_ai.agents.nodes.intake import intake_node
    from eset_incident_ai.agents.nodes.investigate import investigate_node
    from eset_incident_ai.agents.nodes.notify import compose_notification_node, notify_node
    from eset_incident_ai.agents.nodes.remediation import remediation_node
    from eset_incident_ai.agents.nodes.retrieve import retrieve_node
    from eset_incident_ai.agents.nodes.root_cause import root_cause_node
    from eset_incident_ai.agents.nodes.security_review import security_review_node
    from eset_incident_ai.agents.router import (
        route_after_approval,
        route_after_critique,
        route_after_security_review,
    )
    from eset_incident_ai.agents.state import IncidentAgentState

    graph = StateGraph(IncidentAgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("investigate", investigate_node)
    graph.add_node("root_cause", root_cause_node)
    graph.add_node("remediation", remediation_node)
    graph.add_node("critique", critique_node)
    graph.add_node("security_review", security_review_node)
    graph.add_node("approval", approval_node)
    graph.add_node("compose", compose_notification_node)
    graph.add_node("notify", notify_node)
    graph.add_node("reject", reject_node)
    graph.set_entry_point("intake")
    graph.add_edge("intake", "retrieve")
    graph.add_edge("retrieve", "investigate")
    graph.add_edge("investigate", "root_cause")
    graph.add_edge("root_cause", "remediation")
    graph.add_edge("remediation", "critique")
    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "retry_investigation": "investigate",
            "security_review": "security_review",
            "reject": "reject",
        },
    )
    graph.add_conditional_edges(
        "security_review",
        route_after_security_review,
        {"approval": "approval", "compose": "compose", "reject": "reject"},
    )
    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {"approved": "compose", "rejected": "reject", "pending": END},
    )
    graph.add_edge("compose", "notify")
    graph.add_edge("notify", END)
    graph.add_edge("reject", END)
    return graph.compile()
