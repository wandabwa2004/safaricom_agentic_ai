"""Graph construction and compilation."""

from langgraph.graph import StateGraph, END

from graph.state import SimSwapState
from graph.nodes import (
    initiate_request,
    verify_identity,
    check_line_status,
    capture_new_sim,
    block_old_sim,
    provision_new_sim,
    reactivate_mpesa,
    activate_on_network,
    send_confirmation_sms,
    reject_request,
)
from graph.edges import (
    route_after_identity,
    route_after_line_check,
    route_after_sim_validation,
)


def build_graph():
    """Build and compile the SIM swap LangGraph."""
    graph = StateGraph(SimSwapState)

    # Nodes
    graph.add_node("initiate_request", initiate_request)
    graph.add_node("verify_identity", verify_identity)
    graph.add_node("check_line_status", check_line_status)
    graph.add_node("capture_new_sim", capture_new_sim)
    graph.add_node("block_old_sim", block_old_sim)
    graph.add_node("provision_new_sim", provision_new_sim)
    graph.add_node("reactivate_mpesa", reactivate_mpesa)
    graph.add_node("activate_on_network", activate_on_network)
    graph.add_node("send_confirmation_sms", send_confirmation_sms)
    graph.add_node("reject_request", reject_request)

    # Entry
    graph.set_entry_point("initiate_request")

    # Linear edges
    graph.add_edge("initiate_request", "verify_identity")

    # Conditional routing
    graph.add_conditional_edges("verify_identity", route_after_identity, {
        "check_line_status": "check_line_status",
        "reject_request": "reject_request",
        "verify_identity": "verify_identity",
    })
    graph.add_conditional_edges("check_line_status", route_after_line_check, {
        "capture_new_sim": "capture_new_sim",
        "reject_request": "reject_request",
    })
    graph.add_conditional_edges("capture_new_sim", route_after_sim_validation, {
        "block_old_sim": "block_old_sim",
        "capture_new_sim": "capture_new_sim",
        "reject_request": "reject_request",
    })

    # Core swap pipeline (sequential)
    graph.add_edge("block_old_sim", "provision_new_sim")
    graph.add_edge("provision_new_sim", "reactivate_mpesa")
    graph.add_edge("reactivate_mpesa", "activate_on_network")
    graph.add_edge("activate_on_network", "send_confirmation_sms")

    # Terminal
    graph.add_edge("send_confirmation_sms", END)
    graph.add_edge("reject_request", END)

    return graph.compile()


def get_graph_mermaid() -> str:
    """Export the graph as a Mermaid diagram."""
    compiled = build_graph()
    return compiled.get_graph().draw_mermaid()
