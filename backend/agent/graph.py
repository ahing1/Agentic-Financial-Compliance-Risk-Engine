import logging

from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.parse import parse_filing
from agent.nodes.chunk import chunk_and_embed
from agent.nodes.retrieve import retrieve_sections
from agent.nodes.analyze import analyze_risk_factors
from agent.nodes.compare import compare_with_previous
from agent.nodes.verify import verify_citations
from agent.nodes.report import generate_report
from agent.nodes.error import handle_error
from app.config import settings

logger = logging.getLogger(__name__)


def _route_after_verification(state: AgentState) -> str:
    """
    Conditional routing after verification.
    
    Returns a string that maps to the next node via conditional_edges.
    """
    verification_results = state.get("verification_results", [])
    retry_count = state.get("retry_count", 0)
    
    if state.get("error"):
        return "error"
    
    all_verified = all(
        result.get("verified", False)
        for result in verification_results
    )
    
    if all_verified:
        logger.info("All citations verified → report")
        return "report"
    
    if retry_count < settings.max_agent_retries:
        failed = sum(1 for r in verification_results if not r.get("verified", False))
        logger.info(f"{failed} citations failed, retry {retry_count + 1}/{settings.max_agent_retries}")
        return "retrieve"
    
    logger.warning(f"Max retries ({settings.max_agent_retries}) exceeded → error")
    return "error"


def _increment_retry(state: AgentState) -> dict:
    """
    Small node that increments retry counter.
    
    Exists because the retrieve node shouldn't know about retries —
    that's a control flow concern, not a retrieval concern.
    """
    return {
        "retry_count": state.get("retry_count", 0) + 1,
    }


def build_agent_graph() -> StateGraph:
    """
    Construct and compile the LangGraph agent graph.
    
    Returns a compiled graph invokable with:
        result = graph.invoke(initial_state)
    """
    graph = StateGraph(AgentState)
    
    # --- Add nodes ---
    graph.add_node("parse", parse_filing)
    graph.add_node("chunk", chunk_and_embed)
    graph.add_node("retrieve", retrieve_sections)
    graph.add_node("analyze", analyze_risk_factors)
    graph.add_node("compare", compare_with_previous)
    graph.add_node("verify", verify_citations)
    graph.add_node("report", generate_report)
    graph.add_node("error", handle_error)
    graph.add_node("increment_retry", _increment_retry)
    
    # --- Entry point ---
    graph.set_entry_point("parse")
    
    # --- Linear edges ---
    graph.add_edge("parse", "chunk")
    graph.add_edge("chunk", "retrieve")
    graph.add_edge("retrieve", "analyze")
    graph.add_edge("analyze", "compare")
    graph.add_edge("compare", "verify")
    
    # --- Conditional edge after verify ---
    graph.add_conditional_edges(
        "verify",
        _route_after_verification,
        {
            "report": "report",
            "retrieve": "increment_retry",
            "error": "error",
        },
    )
    
    # After incrementing, loop back to retrieve
    graph.add_edge("increment_retry", "retrieve")
    
    # --- Terminal edges ---
    graph.add_edge("report", END)
    graph.add_edge("error", END)
    
    compiled = graph.compile()
    logger.info("Agent graph compiled successfully")
    return compiled


agent_graph = build_agent_graph()