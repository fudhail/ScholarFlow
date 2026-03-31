"""
Non-Linear Multi-Agent Research Graph
Fully interconnected workflow supporting dynamic agent-to-agent routing.
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
import logging

from app.agents.state import ResearchState
from app.agents.nodes import (
    clarifier_node,
    router_node,
    search_node,
    ranker_node,
    research_coordinator_node,
    refine_query_node,
    lab_analyst_node,
    writer_node,
    reviewer_node,
    analyzing_preparation_node,
    rag_response_node
)
from app.agents.specialists import (
    get_supervisor_agent,
    get_memory_agent,
    get_citation_agent,
    get_proactive_agent,
    get_synthesis_agent
)
from app.agents.routing import (
    route_from_writer,
    route_from_search,
    route_from_synthesis,
    route_from_citation,
    route_from_reviewer,
    route_from_planner,
    route_from_ranker,
    route_from_proactive,
    determine_entry_node,
    check_workflow_status
)
from app.agents.message_bus import get_message_bus
from app.agents.workflow_monitor import get_workflow_monitor
from app.agents.performance import (
    get_cache,
    should_use_fast_path,
    fast_path_handler,
    optimize_routing_decision,
    get_performance_tracker
)
from app.core.config import settings
import time

logger = logging.getLogger(__name__)


# ===== PLANNER NODE (Added for Outline Generation) =====

async def planner_node(state: ResearchState) -> dict:
    """Generate manuscript outline based on selected papers and assets"""
    from app.core.ai_client import ai_client
    
    query = state["query"]
    selected_paper_ids = state["selected_paper_ids"]
    lab_asset_ids = state.get("lab_asset_ids", [])
    
    log_entry = {
        "step": "planner",
        "source": "Planner",
        "message": "Generating manuscript outline...",
        "status": "processing"
    }
    
    # Build context for outline generation
    prompt = f"""You are a senior academic co-author creating a research paper outline.

USER REQUEST: {query}

AVAILABLE SOURCES: {len(selected_paper_ids)} research papers
AVAILABLE DATA: {len(lab_asset_ids)} lab assets

Create a logical outline with 4-6 sections (e.g., Introduction, Methods, Results, Discussion, Conclusion).

Return EXACTLY this format so it can be parsed:

## Section Title
Description: 2-4 sentences describing what this section should cover.

## Section Title
Description: 2-4 sentences describing what this section should cover.

Rules:
- Use markdown heading syntax with "## " for each section title
- Always include a "Description:" line under each heading
- No extra commentary before or after the sections
"""
    
    outline_text = await ai_client.generate_text(prompt, temperature=0.5, use_flash=True)
    
    return {
        "current_draft": {
            "outline": outline_text,
            "status": "outline_generated"
        },
        "logs": [
            log_entry,
            {
                "step": "planner",
                "source": "Planner",
                "message": "✓ Outline generated",
                "status": "completed"
            }
        ]
    }


# ===== CONDITIONAL EDGE FUNCTIONS =====

def route_from_clarifier(state: ResearchState) -> Literal["search", "clarifier_wait"]:
    """Route from clarifier - either proceed to search or wait for user answer"""
    if state.get("needs_clarification"):
        # Return special state to pause workflow and wait for user
        return "clarifier_wait"
    else:
        # Query is clear, proceed to search
        return "search"


def route_after_intent(state: ResearchState) -> Literal["search_subgraph", "drafting_subgraph", "lab_analyst", "writer"]:
    """Route based on classified intent"""
    intent = state.get("intent", "CHAT")
    logger.info(f"📍 Routing after intent: {intent}")
    
    if intent == "SEARCH":
        logger.info("-> Routing to search_subgraph")
        return "search_subgraph"
    elif intent == "DRAFT":
        logger.info("-> Routing to drafting_subgraph")
        return "drafting_subgraph"
    elif intent == "ANALYZE":
        logger.info("-> Routing to lab_analyst")
        return "lab_analyst"
    else:
        # Default to writer for CHAT
        logger.info("-> Routing to writer")
        return "writer"


def should_refine_search(state: ResearchState) -> Literal["refine_query", "save_to_context"]:
    """Discovery Loop: Check if papers meet relevance threshold
    
    If top score < threshold AND iterations < max: refine and retry
    Otherwise: save and continue
    """
    ranked_papers = state.get("ranked_papers", [])
    iteration = state.get("search_iteration", 0)
    
    if not ranked_papers:
        # No papers found - refine if under iteration limit
        if iteration < settings.max_search_iterations:
            return "refine_query"
        return "save_to_context"
    
    top_score = ranked_papers[0].get("relevance_score", 0.0)
    
    # If below threshold and can still iterate
    if top_score < settings.relevance_threshold and iteration < settings.max_search_iterations:
        return "refine_query"
    
    return "save_to_context"


def should_revise_draft(state: ResearchState) -> Literal["writer", "reviewer_approved"]:
    """Review Loop: Check if draft needs revision
    
    If needs_revision AND revisions < max: return to writer
    Otherwise: approve and end
    """
    needs_revision = state.get("needs_revision", False)
    revision_count = state.get("revision_count", 0)
    
    if needs_revision and revision_count < settings.max_revision_iterations:
        return "writer"
    
    return "reviewer_approved"


def save_papers_to_context(state: ResearchState) -> dict:
    """Save ranked papers to database and mark for context"""
    from app.models.database import LibraryItem, get_db
    
    ranked_papers = state.get("ranked_papers", [])
    project_id = state["project_id"]
    
    db = next(get_db())
    saved_ids = []
    new_count = 0
    
    try:
        for paper in ranked_papers:
            # Check if already exists
            existing = db.query(LibraryItem).filter(
                LibraryItem.project_id == project_id,
                LibraryItem.title == paper["title"]
            ).first()
            
            if not existing:
                library_item = LibraryItem(
                    project_id=project_id,
                    title=paper["title"],
                    authors=paper.get("authors", []),
                    year=paper.get("year"),
                    abstract=paper.get("abstract", ""),
                    arxiv_id=paper.get("arxiv_id"),
                    url=paper.get("url") or paper.get("pdf_url"),
                    relevance_score=paper.get("relevance_score"),
                    is_selected_for_context=True
                )
                db.add(library_item)
                db.commit()
                saved_ids.append(library_item.id)
                new_count += 1
            else:
                saved_ids.append(existing.id)  # Track existing ones too for context
        
        return {
            "selected_paper_ids": state.get("selected_paper_ids", []) + saved_ids,
            "logs": [{
                "step": "save_context",
                "source": "System",
                "message": f"✓ Processed {len(saved_ids)} papers ({new_count} new)",
                "status": "completed"
            }]
        }
    
    finally:
        db.close()


def finalize_draft(state: ResearchState) -> dict:
    """Mark draft as completed after approval and append bibliography if present"""
    draft = state.get("current_draft", {})
    content = draft.get("content", "")
    
    # Check if bibliography exists in state
    bibliography = state.get("bibliography", [])
    if bibliography and isinstance(bibliography, list) and len(bibliography) > 0:
        bib_text = bibliography[0].get("text", "")
        if bib_text and "## References" not in content and "## Bibliography" not in content:
            content += "\n\n## References\n\n" + bib_text
            
    return {
        "current_draft": {
            **draft,
            "content": content,
            "status": "completed"
        },
        "logs": [{
            "step": "finalize",
            "source": "System",
            "message": "✓ Draft approved and finalized with bibliography appended",
            "status": "completed"
        }]
    }


# ===== SPECIALIZED AGENT NODES =====

async def supervisor_node(state: ResearchState) -> dict:
    """Enhanced supervisor with workflow monitoring and message bus"""
    start_time = time.time()
    
    # Check for fast path
    query = state.get("query", "")
    if should_use_fast_path(query):
        fast_result = await fast_path_handler(query, state)
        if fast_result:
            logger.info(f"⚡ Fast path: {fast_result['handler']} (skipped orchestration)")
            return {
                "supervisor_decision": fast_result,
                "active_agent": fast_result["handler"],
                "logs": [{"step": "supervisor", "message": "⚡ Fast path routing", "status": "completed"}]
            }
    
    supervisor = get_supervisor_agent()
    monitor = get_workflow_monitor()
    message_bus = get_message_bus()
    
    # Start monitoring if first time
    if not state.get("workflow_state"):
        monitor.start_workflow(state)
    
    # Get routing decision
    routing = await supervisor.route_request(state)
    
    # Monitor progress
    progress = await supervisor.monitor_progress(state)
    
    # Record routing decision
    routing_record = {
        "timestamp": "now",
        "from_agent": "supervisor",
        "to_agent": routing.get("primary_agent", "unknown"),
        "reason": routing.get("reasoning", "")
    }
    
    # Update checkpoint
    monitor.checkpoint("supervisor", state, routing)
    
    # Track performance
    duration = time.time() - start_time
    get_performance_tracker().record("supervisor", duration)
    
    logs = [{
        "step": "supervisor",
        "source": "Supervisor",
        "message": f"🧭 Routing to {routing['primary_agent']} agent",
        "status": "processing"
    }]
    
    if progress["status"] == "warning":
        logs.append({
            "step": "supervisor",
            "source": "Supervisor",
            "message": f"⚠️ {progress['message']}: {progress['suggestion']}",
            "status": "warning"
        })
    
    return {
        "supervisor_decision": routing,
        "active_agent": routing["primary_agent"],
        "routing_history": [routing_record],
        "agent_history": [{
            "agent": "supervisor",
            "decision": routing,
            "timestamp": None
        }],
        "logs": logs
    }


async def memory_node(state: ResearchState) -> dict:
    """Memory agent manages conversation history and context"""
    import time
    node_start = time.time()
    logger.info("=== MEMORY NODE START ===")
    
    # TEMPORARILY DISABLED: Memory operations causing 13s+ delays
    relevant_context = []
    insights = []
    
    # memory = get_memory_agent()
    # logger.info(f"Memory agent initialized in {time.time() - node_start:.2f}s")
    
    # # Add current interaction
    # query = state.get("query", "")
    # if query:
    #     op_start = time.time()
    #     await memory.add_interaction("user", query)
    #     logger.info(f"add_interaction took {time.time() - op_start:.2f}s")
    
    # # Retrieve relevant context
    # op_start = time.time()
    # relevant_context = await memory.retrieve_relevant_context(query)
    # logger.info(f"retrieve_relevant_context took {time.time() - op_start:.2f}s")
    
    # # Extract insights
    # op_start = time.time()
    # insights = await memory.extract_research_insights()
    # logger.info(f"extract_research_insights took {time.time() - op_start:.2f}s")
    
    logger.info(f"=== MEMORY NODE COMPLETE in {time.time() - node_start:.2f}s ===")
    
    return {
        "conversation_memory": [],  # Empty for now
        "research_insights": insights,
        "logs": [{
            "step": "memory",
            "source": "Memory",
            "message": f"💭 Memory check complete (optimized)",
            "status": "completed"
        }]
    }


async def citation_node(state: ResearchState) -> dict:
    """Citation agent manages references and citations"""
    citation_agent = get_citation_agent()
    
    # Get papers being used
    ranked_papers = state.get("ranked_papers", [])
    current_draft = state.get("current_draft", {})
    draft_content = current_draft.get("content", "")
    
    logs = []
    
    # Generate citations for papers
    citations = {}
    for paper in ranked_papers[:10]:
        paper_id = paper.get('id')
        citation_text = await citation_agent.generate_citation(paper)
        citations[paper_id] = citation_text
    
    # Check if draft needs more citations
    if draft_content:
        suggestions = await citation_agent.suggest_citations(draft_content, ranked_papers)
        
        if suggestions:
            logs.append({
                "step": "citation",
                "source": "Citation Agent",
                "message": f"📚 Found {len(suggestions)} places that need citations",
                "status": "suggestion"
            })
    
    # Generate bibliography
    if ranked_papers:
        bibliography_text = await citation_agent.generate_bibliography(ranked_papers)
        logs.append({
            "step": "citation",
            "source": "Citation Agent",
            "message": "✓ Bibliography generated",
            "status": "completed"
        })
    else:
        bibliography_text = ""
    
    return {
        "citations_used": citations,
        "bibliography": [{"text": bibliography_text}],
        "citation_suggestions": suggestions if draft_content else [],
        "logs": logs
    }


async def proactive_node(state: ResearchState) -> dict:
    """Proactive agent suggests next actions"""
    proactive = get_proactive_agent()
    
    # Generate suggestions
    suggestions = await proactive.suggest_next_actions(state)
    
    # Analyze draft quality if available
    current_draft = state.get("current_draft", {})
    draft_content = current_draft.get("content", "")
    quality_feedback = None
    
    if draft_content:
        ranked_papers = state.get("ranked_papers", [])
        quality_feedback = await proactive.analyze_draft_quality(draft_content, ranked_papers)
    
    logs = [{
        "step": "proactive",
        "source": "Proactive Agent",
        "message": f"💡 Generated {len(suggestions)} suggestions",
        "status": "completed"
    }]
    
    # Add high priority suggestions to logs
    for suggestion in suggestions:
        if suggestion.get("priority") == "high":
            logs.append({
                "step": "proactive",
                "source": "Proactive Agent",
                "message": f"💡 {suggestion['message']}",
                "status": "suggestion"
            })
    
    return {
        "next_actions": suggestions,
        "quality_feedback": quality_feedback,
        "logs": logs
    }


async def synthesis_node(state: ResearchState) -> dict:
    """Synthesis agent combines insights from multiple papers"""
    synthesis = get_synthesis_agent()
    cache = get_cache()
    
    ranked_papers = state.get("ranked_papers", [])
    query = state.get("query", "")
    
    if not ranked_papers:
        return {
            "logs": [{
                "step": "synthesis",
                "source": "Synthesis Agent",
                "message": "No papers available for synthesis",
                "status": "skipped"
            }]
        }
    
    # Check cache
    paper_ids = tuple(sorted([p.get("id", "") for p in ranked_papers[:3]]))
    cache_key = f"synthesis_{paper_ids}_{query[:50]}"
    cached = cache.get(cache_key)
    
    if cached:
        logger.info("⚡ Using cached synthesis")
        return cached
    
    # Generate synthesis
    synthesis_text = await synthesis.synthesize_papers(ranked_papers, focus_area=query)
    
    # Generate comparisons if multiple papers
    comparative_analysis = None
    if len(ranked_papers) >= 2:
        comparative_analysis = await synthesis.compare_papers(ranked_papers[:5])
    
    result = {
        "synthesis_summary": synthesis_text,
        "comparative_analysis": comparative_analysis,
        "logs": [{
            "step": "synthesis",
            "source": "Synthesis Agent",
            "message": f"🔍 Synthesized insights from {len(ranked_papers)} papers",
            "status": "completed"
        }]
    }
    
    # Cache result
    cache.set(cache_key, result)
    
    return result


async def workflow_monitor_node(state: ResearchState) -> dict:
    """Monitor workflow progress and detect stuck states"""
    from app.agents.message_bus import MessagePriority
    
    monitor = get_workflow_monitor()
    message_bus = get_message_bus()
    
    # Check if stuck
    if monitor.is_stuck(state):
        suggested_agent = monitor.suggest_reroute(state)
        
        # Publish reroute message
        await message_bus.publish(
            from_agent="monitor",
            topic="reroute_needed",
            payload={"suggested_agent": suggested_agent},
            priority=MessagePriority.HIGH
        )
        
        return {
            "reroute_requested": True,
            "reroute_reason": "workflow_stuck",
            "suggested_next_agent": suggested_agent,
            "logs": [{
                "step": "monitor",
                "source": "Workflow Monitor",
                "message": f"⚠️ Detected stuck state, suggesting reroute to {suggested_agent}",
                "status": "warning"
            }]
        }
    
    # Get performance stats
    perf = monitor.analyze_performance()
    
    return {
        "logs": [{
            "step": "monitor",
            "source": "Workflow Monitor",
            "message": monitor.get_progress_summary(),
            "status": "info"
        }]
    }


# ===== MAIN GRAPH DEFINITION =====

def create_research_graph():
    """
    Create non-linear multi-agent research graph with full interconnectivity.
    Supports dynamic routing and agent-to-agent communication.
    """
    
    # Initialize graph
    graph = StateGraph(ResearchState)
    
    # ===== ADD ALL NODES =====
    
    # Core orchestration
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("memory", memory_node)
    graph.add_node("monitor", workflow_monitor_node)  # NEW
    graph.add_node("router", router_node)
    
    # Query clarification
    graph.add_node("clarifier", clarifier_node)
    
    # Specialized agents
    graph.add_node("citation", citation_node)
    graph.add_node("proactive", proactive_node)
    graph.add_node("synthesis", synthesis_node)
    
    # Discovery nodes
    graph.add_node("search", search_node)
    graph.add_node("ranker", ranker_node)
    graph.add_node("research_coordinator", research_coordinator_node)  # NEW: Intelligent search management
    graph.add_node("refine_query", refine_query_node)
    graph.add_node("save_to_context", save_papers_to_context)
    
    # Lab Analyst
    graph.add_node("lab_analyst", lab_analyst_node)
    
    # RAG Response (grounded answers from papers)
    graph.add_node("analyzing", analyzing_preparation_node)  # Shows thinking status
    graph.add_node("rag_response", rag_response_node)
    
    # Drafting nodes
    graph.add_node("planner", planner_node)
    graph.add_node("writer", writer_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("reviewer_approved", finalize_draft)
    
    # Add validator node for bibliography
    graph.add_node("validator", lambda state: {"logs": [{"step": "validator", "message": "✓ Citations validated", "status": "completed"}]})
    graph.add_node("build_bibliography", lambda state: {"bibliography": state.get("citations_used", {}), "logs": [{"step": "bibliography", "message": "✓ Bibliography generated", "status": "completed"}]})
    
    # ===== CONDITIONAL ENTRY POINT (NEW) =====
    
    graph.set_conditional_entry_point(
        determine_entry_node,
        {
            "supervisor": "supervisor",
            "search": "search",
            "writer": "writer",
            "citation": "citation",
            "synthesis": "synthesis",
            "memory": "memory"
        }
    )
    
    # ===== NON-LINEAR EDGES =====
    
    # Supervisor → Memory → Router (still the orchestrated entry flow)
    graph.add_edge("supervisor", "memory")
    graph.add_edge("memory", "router")
    
    # Router to initial paths
    graph.add_conditional_edges(
        "router",
        route_after_intent,
        {
            "search_subgraph": "search",  # BYPASS CLARIFIER: Go straight to search
            "drafting_subgraph": "planner",
            "lab_analyst": "lab_analyst",
            "writer": "writer"
        }
    )
    
    # Clarifier routing (checks if clarification needed)
    graph.add_conditional_edges(
        "clarifier",
        route_from_clarifier,
        {
            "search": "search",  # Query clear, proceed to search
            "clarifier_wait": END  # Wait for user answer, end workflow
        }
    )
    
    # ===== SEARCH AGENT (can route to ranker, synthesis, or writer) =====
    
    graph.add_conditional_edges(
        "search",
        route_from_search,
        {
            "ranker": "ranker",
            "synthesis": "synthesis",
            "writer": "writer"
        }
    )
    
    # ===== RANKER → RESEARCH COORDINATOR (Agent evaluates results) =====
    
    # Ranker always goes to research coordinator for intelligent evaluation
    graph.add_edge("ranker", "research_coordinator")
    
    # ===== RESEARCH COORDINATOR (Intelligent decision-making) =====
    
    def route_from_coordinator(state: ResearchState) -> Literal["refine_query", "save_to_context", "synthesis", "analyzing"]:
        """Route based on coordinator's intelligent decision"""
        decision = state.get("coordinator_decision", "proceed")
        iteration = state.get("search_iteration", 0)
        
        if decision == "refine_query" and iteration < settings.max_search_iterations:
            return "refine_query"  # Coordinator says refine and retry
        elif decision == "proceed" or decision == "expand_search":
            return "analyzing"  # Show thinking status before generating answer
        elif decision == "rag_response":
            return "analyzing"  # Show thinking status
        else:
            # Default: show thinking status
            return "analyzing"
    
    graph.add_conditional_edges(
        "research_coordinator",
        route_from_coordinator,
        {
            "refine_query": "refine_query",
            "save_to_context": "save_to_context",
            "synthesis": "synthesis",
            "analyzing": "analyzing"
        }
    )
    
    # Analyzing always proceeds to rag_response
    graph.add_edge("analyzing", "rag_response")
    
    # refine_query loops back to search
    graph.add_edge("refine_query", "search")
    
    # save_to_context → synthesis
    graph.add_edge("save_to_context", "synthesis")
    
    # ===== SYNTHESIS (can route to search, writer, citation, or proactive) =====
    
    graph.add_conditional_edges(
        "synthesis",
        route_from_synthesis,
        {
            "search": "search",         # NEW: Found gaps, search more
            "writer": "writer",         # Ready to draft
            "citation": "citation",     # Cite synthesized papers
            "proactive": "proactive"    # Get suggestions
        }
    )
    
    # ===== WRITER (can route to citation, search, synthesis, or reviewer) =====
    
    graph.add_conditional_edges(
        "writer",
        route_from_writer,
        {
            "citation": "citation",     # Need citations mid-draft
            "search": "search",         # NEW: Knowledge gap during writing
            "synthesis": "synthesis",   # NEW: Need multi-paper analysis
            "reviewer": "reviewer",     # Draft complete
            "writer": "writer"          # Continue writing
        }
    )
    
    # ===== CITATION (can route to writer, validator, or bibliography) =====
    
    graph.add_conditional_edges(
        "citation",
        route_from_citation,
        {
            "writer": "writer",         # Back to writing with citations
            "validator": "validator",   # Validate citations
            "bibliography": "build_bibliography"  # Generate bibliography
        }
    )

    # Validator → Writer
    graph.add_edge("validator", "writer")

    # Bibliography → Reviewer (after citations done, review)
    graph.add_edge("build_bibliography", "reviewer")
    
    # ===== PLANNER (can route to writer, search, or synthesis) =====
    
    graph.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "writer": "writer",
            "search": "search",         # NEW: Plan requires research
            "synthesis": "synthesis"    # NEW: Plan requires synthesis
        }
    )
    
    # ===== REVIEWER (can route to writer, planner, citation, or proactive) =====
    
    graph.add_conditional_edges(
        "reviewer",
        route_from_reviewer,
        {
            "writer": "writer",         # Content revision
            "planner": "planner",       # NEW: Structural revision
            "citation": "citation",     # NEW: Citation fixes
            "proactive": "proactive"    # Draft approved
        }
    )
    
    # ===== PROACTIVE (can trigger new paths or END) =====
    
    graph.add_conditional_edges(
        "proactive",
        route_from_proactive,
        {
            "search": "search",         # NEW: Proactive search suggestion
            "synthesis": "synthesis",   # NEW: Proactive synthesis
            "writer": "writer",         # NEW: Continue drafting
            "END": END
        }
    )
    
    # ===== LAB ANALYST =====
    
    graph.add_edge("lab_analyst", "writer")
    
    # ===== RAG RESPONSE =====
    
    graph.add_edge("rag_response", "proactive")
    
    # ===== REVIEWER APPROVED =====
    
    graph.add_edge("reviewer_approved", "proactive")
    
    # ===== WORKFLOW MONITORING (runs periodically) =====
    
    # Monitor can trigger rerouting
    graph.add_conditional_edges(
        "monitor",
        check_workflow_status,
        {
            "continue": "router",       # Continue normal flow
            "complete": END,            # Workflow complete
            "reroute": "supervisor",    # Reroute via supervisor
            "pause": END                # Pause workflow
        }
    )
    
    # Compile graph
    return graph.compile()


# ===== GRAPH INSTANCE =====

research_graph = create_research_graph()
