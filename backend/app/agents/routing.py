"""
Dynamic routing functions for non-linear research workflows.
Enables agents to route to each other based on context and needs.
Optimized for fast response times.
"""
from typing import Literal
import logging
from app.agents.state import ResearchState
from app.agents.message_bus import get_message_bus, MessageTopics

logger = logging.getLogger(__name__)


def optimize_routing_decision(state: ResearchState) -> str:
    """
    Make faster routing decisions by checking simple rules first.
    Returns immediate decision or None if needs full routing logic.
    """
    draft = state.get("current_draft", {})
    content = draft.get("content", "")
    
    # Immediate decisions based on content markers
    if "[CITE]" in content or "citation needed" in content.lower():
        return "citation"
    if "TODO:" in content or "[FIND]" in content:
        return "search"
    if "[SYNTHESIZE]" in content:
        return "synthesis"
    if draft.get("status") == "complete":
        return "reviewer"
    
    # Check limits
    if state.get("revision_count", 0) >= 3:
        return "search"  # Get fresh insights
    
    return None


def route_from_writer(state: ResearchState) -> Literal["citation", "search", "reviewer", "writer", "synthesis"]:
    """
    Dynamic routing from writer agent based on draft needs.
    Enables non-linear transitions during writing.
    Optimized for speed with quick rule checks.
    
    Returns:
        Next agent to route to
    """
    # Fast optimization check
    quick_decision = optimize_routing_decision(state)
    if quick_decision:
        logger.info(f"⚡ Quick routing: writer → {quick_decision}")
        return quick_decision
    
    draft = state.get("current_draft", {})
    content = draft.get("content", "")
    
    # Check for citation placeholders or requests
    if "[?]" in content or "citation needed" in content.lower() or "[CITE]" in content:
        logger.info("🔀 Writer → Citation (citations needed)")
        return "citation"
    
    # Check for knowledge gaps or TODO markers
    if "TODO:" in content or "RESEARCH:" in content or "[FIND]" in content:
        logger.info("🔀 Writer → Search (knowledge gap detected)")
        return "search"
    
    # Check for synthesis requests
    if "[SYNTHESIZE]" in content or "compare papers" in content.lower():
        logger.info("🔀 Writer → Synthesis (multi-paper analysis needed)")
        return "synthesis"
    
    # Check if draft section is complete
    status = draft.get("status", "")
    if status == "complete" or draft.get("ready_for_review", False):
        logger.info("🔀 Writer → Reviewer (draft complete)")
        return "reviewer"
    
    # Check revision count - if too many, might be stuck
    revision_count = state.get("revision_count", 0)
    if revision_count >= 3:
        logger.warning("⚠️  Writer stuck (3+ revisions), routing to search for new insights")
        return "search"
    
    # Default: continue writing
    logger.debug("🔀 Writer → Writer (continue drafting)")
    return "writer"


def route_from_search(state: ResearchState) -> Literal["ranker", "synthesis", "writer"]:
    """
    Route from search based on what triggered the search.
    
    Returns:
        Next agent to route to
    """
    # Check routing history to see what called search
    routing_history = state.get("routing_history", [])
    
    if routing_history:
        last_route = routing_history[-1]
        caller = last_route.get("from_agent", "")
        
        # If writer called search, go back to writer after ranking
        if caller == "writer":
            logger.info("🔀 Search → Ranker → Writer (returning to draft)")
            return "ranker"  # Will eventually route back to writer
        
        # If synthesis called search, go back to synthesis
        if caller == "synthesis":
            logger.info("🔀 Search → Synthesis (new papers for analysis)")
            return "synthesis"
    
    # Check if we have papers to rank
    found_papers = state.get("found_papers", [])
    if found_papers and len(found_papers) > 1:
        logger.info("🔀 Search → Ranker (ranking papers)")
        return "ranker"
    
    # Default: synthesis for single paper or no papers
    logger.info("🔀 Search → Synthesis (direct analysis)")
    return "synthesis"


def route_from_synthesis(state: ResearchState) -> Literal["search", "writer", "citation", "proactive"]:
    """
    Route from synthesis based on findings.
    Enables discovery-driven workflow changes.
    
    Returns:
        Next agent to route to
    """
    synthesis_summary = state.get("synthesis_summary", "")
    
    # Check for contradictions (trigger new search)
    if "contradiction" in synthesis_summary.lower() or "conflicting" in synthesis_summary.lower():
        logger.info("🔀 Synthesis → Search (contradictions found, need more sources)")
        return "search"
    
    # Check for identified gaps (trigger new search)
    if "gap" in synthesis_summary.lower() or "missing" in synthesis_summary.lower() or "lack" in synthesis_summary.lower():
        logger.info("🔀 Synthesis → Search (research gaps identified)")
        return "search"
    
    # Check for citation opportunities
    comparative_analysis = state.get("comparative_analysis", {})
    if comparative_analysis and len(comparative_analysis.get("papers", [])) > 2:
        logger.info("🔀 Synthesis → Citation (multiple papers to cite)")
        return "citation"
    
    # Check if drafting is in progress
    current_draft = state.get("current_draft", {})
    if current_draft and current_draft.get("status") == "in_progress":
        logger.info("🔀 Synthesis → Writer (returning to draft with insights)")
        return "writer"
    
    # Default: proceed to writer
    logger.info("🔀 Synthesis → Writer (starting draft)")
    return "writer"


def route_from_citation(state: ResearchState) -> Literal["writer", "validator", "bibliography"]:
    """
    Route from citation agent based on citation state.
    
    Returns:
        Next agent to route to
    """
    citation_suggestions = state.get("citation_suggestions", [])
    citations_used = state.get("citations_used", {})
    
    # Check for high-priority suggestions that need validation
    high_priority = [s for s in citation_suggestions if s.get("priority") == "high"]
    if high_priority and len(high_priority) > 3:
        logger.info("🔀 Citation → Validator (many high-priority suggestions)")
        return "validator"
    
    # Check if bibliography needs generation
    if len(citations_used) > 5 and not state.get("bibliography"):
        logger.info("🔀 Citation → Bibliography (generating references)")
        return "bibliography"
    
    # Default: back to writer
    logger.info("🔀 Citation → Writer (citations added, continue writing)")
    return "writer"


def route_from_reviewer(state: ResearchState) -> Literal["writer", "planner", "citation", "proactive"]:
    """
    Route from reviewer based on feedback.
    Enables restructuring or targeted improvements.
    
    Returns:
        Next agent to route to
    """
    critique = state.get("critique_feedback", "")
    needs_revision = state.get("needs_revision", False)
    
    if not needs_revision:
        logger.info("🔀 Reviewer → Proactive (draft approved)")
        return "proactive"
    
    # Check for structural issues (trigger planner)
    structural_keywords = ["structure", "organization", "flow", "reorganize", "reorder"]
    if any(keyword in critique.lower() for keyword in structural_keywords):
        logger.info("🔀 Reviewer → Planner (structural revision needed)")
        return "planner"
    
    # Check for citation issues
    citation_keywords = ["citation", "reference", "source", "cite"]
    if any(keyword in critique.lower() for keyword in citation_keywords):
        logger.info("🔀 Reviewer → Citation (citation improvements needed)")
        return "citation"
    
    # Default: back to writer for content revision
    logger.info("🔀 Reviewer → Writer (content revision needed)")
    return "writer"


def route_from_planner(state: ResearchState) -> Literal["writer", "search", "synthesis"]:
    """
    Route from planner based on plan.
    
    Returns:
        Next agent to route to
    """
    current_draft = state.get("current_draft", {})
    plan = current_draft.get("plan", {})
    
    # Check if plan requires new research
    if plan.get("needs_research", False):
        logger.info("🔀 Planner → Search (plan requires new research)")
        return "search"
    
    # Check if plan requires synthesis
    if plan.get("needs_synthesis", False):
        logger.info("🔀 Planner → Synthesis (plan requires multi-paper analysis)")
        return "synthesis"
    
    # Default: proceed to writing
    logger.info("🔀 Planner → Writer (executing plan)")
    return "writer"


def route_from_ranker(state: ResearchState) -> Literal["refine_query", "save_to_context", "synthesis", "rag_response"]:
    """
    Route from ranker based on ranking results.
    Implements the Discovery Loop.
    
    Returns:
        Next agent to route to
    """
    ranked_papers = state.get("ranked_papers", [])
    search_iteration = state.get("search_iteration", 0)
    query = state.get("query", "").lower()
    
    # Check if we have good papers
    if ranked_papers:
        # Check relevance scores
        avg_relevance = sum(p.get("relevance_score", 0) for p in ranked_papers[:3]) / min(3, len(ranked_papers))
        
        # If low relevance and haven't tried too many times
        if avg_relevance < 0.6 and search_iteration < 3:
            logger.info(f"🔀 Ranker → Refine Query (low relevance: {avg_relevance:.2f})")
            return "refine_query"
    
        # If no good papers after 3 iterations, save what we have
        if search_iteration >= 3 and not ranked_papers:
             logger.info("🔀 Ranker → Save Context (max iterations reached, no papers)")
             return "save_to_context"
             
    # CHECK FOR EXPLICIT SYNTHESIS REQUEST
    if "synthesize" in query or "compare" in query or "meta-analysis" in query:
        logger.info("🔀 Ranker → Synthesis (explicit synthesis requested)")
        return "synthesis"

    # Default for good papers -> RAG Response (Q&A)
    # This ensures "Answer + Citations" format instead of raw synthesis
    if ranked_papers:
        logger.info("🔀 Ranker → RAG Response (answering user query)")
        return "rag_response"
    
    # Fallback
    logger.info("🔀 Ranker → Save Context (fallback)")
    return "save_to_context"


def route_from_proactive(state: ResearchState) -> Literal["search", "writer", "synthesis", "END"]:
    """
    Route from proactive agent based on suggestions.
    Can trigger new research directions.
    
    Returns:
        Next agent to route to or END
    """
    next_actions = state.get("next_actions", [])
    
    # Check for high-priority actions
    high_priority_actions = [a for a in next_actions if a.get("priority") == "high"]
    
    if high_priority_actions:
        action_type = high_priority_actions[0].get("type", "")
        
        if action_type == "search":
            logger.info("🔀 Proactive → Search (high-priority search suggested)")
            return "search"
        
        if action_type == "synthesis":
            logger.info("🔀 Proactive → Synthesis (synthesis suggested)")
            return "synthesis"
        
        if action_type == "draft":
            logger.info("🔀 Proactive → Writer (drafting suggested)")
            return "writer"
    
    # Check workflow state
    workflow_state = state.get("workflow_state", "running")
    if workflow_state == "complete":
        logger.info("🔀 Proactive → END (workflow complete)")
        return "END"
    
    # Default: end
    logger.info("🔀 Proactive → END (no high-priority actions)")
    return "END"


def determine_entry_node(state: ResearchState) -> Literal["supervisor", "search", "writer", "citation", "synthesis", "memory"]:
    """
    Determine entry point based on task type.
    Enables direct agent invocation for efficiency.
    
    Returns:
        Entry node name
    """
    query = state.get("query", "").lower()
    intent = state.get("intent", "")
    
    # Direct citation task
    if "add citation" in query or "cite" in query and len(query.split()) < 10:
        logger.info("🚪 Entry → Citation (direct citation task)")
        return "citation"
    
    # Direct search task
    if intent == "SEARCH" or "search for" in query or "find papers" in query:
        logger.info("🚪 Entry → Search (direct search task)")
        return "search"
    
    # Direct synthesis task
    if "compare papers" in query or "synthesize" in query or "analyze papers" in query:
        logger.info("🚪 Entry → Synthesis (direct synthesis task)")
        return "synthesis"
    
    # Direct writing task
    if "write" in query or "draft" in query or intent == "DRAFT":
        logger.info("🚪 Entry → Writer (direct writing task)")
        return "writer"
    
    # Context/memory query
    if "remember" in query or "context" in query or "previous" in query:
        logger.info("🚪 Entry → Memory (context retrieval)")
        return "memory"
    
    # Default: supervisor for orchestration
    logger.info("🚪 Entry → Supervisor (default orchestration)")
    return "supervisor"


def check_workflow_status(state: ResearchState) -> Literal["continue", "complete", "reroute", "pause"]:
    """
    Check overall workflow status for continuous monitoring.
    
    Returns:
        Workflow status decision
    """
    workflow_state = state.get("workflow_state", "running")
    
    # Check if reroute requested
    if state.get("reroute_requested", False):
        logger.info("📊 Workflow Status → Reroute (requested)")
        return "reroute"
    
    # Check if paused
    if workflow_state == "paused":
        logger.info("📊 Workflow Status → Pause")
        return "pause"
    
    # Check if complete
    if workflow_state == "complete":
        logger.info("📊 Workflow Status → Complete")
        return "complete"
    
    # Check if stuck (based on iteration counts)
    revision_count = state.get("revision_count", 0)
    search_iteration = state.get("search_iteration", 0)
    
    if revision_count > 3 or search_iteration > 3:
        logger.warning("📊 Workflow Status → Reroute (possible stuck state)")
        return "reroute"
    
    # Default: continue
    logger.debug("📊 Workflow Status → Continue")
    return "continue"


def should_run_parallel(state: ResearchState) -> bool:
    """
    Determine if tasks can be run in parallel.
    
    Returns:
        True if parallel execution is beneficial
    """
    ranked_papers = state.get("ranked_papers", [])
    found_papers = state.get("found_papers", [])
    
    # Parallel analysis if multiple papers
    if len(ranked_papers) >= 3 or len(found_papers) >= 5:
        logger.info("⚡ Parallel execution enabled (multiple papers)")
        return True
    
    # Parallel if both synthesis and citation needed
    needs_synthesis = state.get("synthesis_summary") is None and ranked_papers
    needs_citation = len(state.get("citations_used", {})) == 0 and ranked_papers
    
    if needs_synthesis and needs_citation:
        logger.info("⚡ Parallel execution enabled (synthesis + citation)")
        return True
    
    return False


# ============================================================
# PHASE 2–4 ROUTING FUNCTIONS
# ============================================================

def route_after_interrupt(state: ResearchState) -> Literal["supervisor", "END"]:
    """
    After interrupt_handler: if interrupted → END, otherwise continue to supervisor.
    """
    if state.get("interrupted"):
        logger.info("🛑 Routing → END (user interrupted)")
        return "END"
    logger.debug("▶ Routing → supervisor (no interrupt)")
    return "supervisor"


def route_after_guardrail(state: ResearchState) -> Literal["router", "clarifier", "guardrail_response", "deep_rag_pipeline"]:
    """
    After intent_guardrail_node:
    • ALLOW  → router (normal flow)
    • ALLOW + DEEP_RESEARCH → deep_rag_pipeline (bypass general router)
    • CLARIFY → clarifier (ask user for clarification)
    • BLOCK  → guardrail_response (return blocked message)
    """
    status = state.get("intent_guardrail_status", "ALLOW")
    guarded_intent = (state.get("intent_guarded") or "").upper()
    if status == "BLOCK":
        logger.info("🚫 Guardrail routing → guardrail_response")
        return "guardrail_response"
    if status == "CLARIFY":
        logger.info("❓ Guardrail routing → clarifier")
        return "clarifier"
    if guarded_intent == "DEEP_RESEARCH":
        logger.info("🔬 Guardrail routing → deep_rag_pipeline")
        return "deep_rag_pipeline"
    logger.info("✅ Guardrail routing → router")
    return "router"


def route_after_llm_gate(state: ResearchState) -> Literal["planner", "deterministic_handler"]:
    """
    After llm_necessity_gate:
    • needs_llm=True  → planner
    • needs_llm=False → deterministic_handler
    """
    if state.get("needs_llm", True):
        logger.info("🧠 LLM gate → planner")
        return "planner"
    logger.info("⚡ LLM gate → deterministic_handler")
    return "deterministic_handler"


def route_after_planner_reviewer(state: ResearchState) -> Literal["planner", "search", "writer", "synthesis"]:
    """
    After planner_reviewer_node:
    • REVISE  → planner (re-plan)
    • APPROVED → downstream (search/writer/synthesis based on plan)
    """
    review_status = state.get("planner_review_status", "APPROVED")
    if review_status == "REVISE":
        logger.info("🔁 Planner reviewer → planner (revision requested)")
        return "planner"

    # APPROVED — use planner's own routing logic
    return route_from_planner(state)


def route_after_guardrail_response(state: ResearchState) -> Literal["END"]:
    """Terminal routing for blocked queries."""
    return "END"

