from langgraph.graph import StateGraph, END

from app.agents.state import GraphState
from app.agents.ingestion_agent import ingestion_agent
from app.agents.verification_agent import verification_agent
from app.agents.prioritization_agent import prioritization_agent
from app.agents.allocation_agent import allocation_agent
from app.agents.communication_agent import communication_agent


def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph.

    Node execution order (linear — no conditional branches in MVP):
        START → ingestion → verification → prioritization → allocation → communication → END

    Each node is an async function that receives GraphState and returns
    an updated GraphState. LangGraph merges returned keys back into the
    shared state dict before passing to the next node.
    """
    graph = StateGraph(GraphState)

    # Register agent nodes
    graph.add_node("ingestion", ingestion_agent)
    graph.add_node("verification", verification_agent)
    graph.add_node("prioritization", prioritization_agent)
    graph.add_node("allocation", allocation_agent)
    graph.add_node("communication", communication_agent)

    # Define linear edge chain
    graph.set_entry_point("ingestion")
    graph.add_edge("ingestion", "verification")
    graph.add_edge("verification", "prioritization")
    graph.add_edge("prioritization", "allocation")
    graph.add_edge("allocation", "communication")
    graph.add_edge("communication", END)

    return graph


# Module-level compiled graph — imported by scheduler and /agents/run router.
# Compiled once at import time; thread-safe for concurrent invocations.
compiled_graph = build_graph().compile()
