"""Individual LangGraph node implementations"""

from typing import Dict
from langchain_core.messages import HumanMessage, AIMessage
import httpx
import logging
from sqlalchemy.orm import Session

from app.agents.state import ResearchState
from app.core.ai_client import ai_client
from app.core.config import settings
from app.models.database import LibraryItem, LabAsset, get_db
from app.services.vector_store import vector_store
from app.services.rag_grounding import generate_grounded_response, format_paper_context
from app.agents.specialists import get_memory_agent, get_citation_agent

logger = logging.getLogger(__name__)


_FACTUAL_CHAT_PREFIXES = (
    "what is", "what are", "who is", "who are", "how does", "why does",
    "explain", "define", "tell me about",
)


def _is_factual_chat_query(query: str) -> bool:
    q = (query or "").lower().strip()
    return any(q.startswith(prefix) for prefix in _FACTUAL_CHAT_PREFIXES)


def _has_prior_research_context(state: ResearchState) -> bool:
    return bool(
        state.get("selected_paper_ids")
        or state.get("ranked_papers")
        or state.get("found_papers")
    )


# ===== CLARIFIER NODE =====

async def clarifier_node(state: ResearchState) -> Dict:
    """Check query ambiguity and ask clarifying questions if needed"""
    
    query = state["query"]
    clarification_answer = state.get("clarification_answer")
    
    # If we already have a clarification answer, refine the query
    if clarification_answer:
        refined_query = f"{query} (specifically: {clarification_answer})"
        return {
            "query": refined_query,
            "needs_clarification": False,
            "logs": [{
                "step": "clarifier",
                "source": "Clarifier",
                "message": f"✓ Query refined based on clarification: {clarification_answer}",
                "status": "completed"
            }]
        }
    
    # Analyze query ambiguity
    log_entry = {
        "step": "clarifier",
        "source": "Clarifier",
        "message": "Analyzing query clarity...",
        "status": "processing"
    }
    
    # Use AI to detect ambiguity
    prompt = f"""Analyze this research query for ambiguity on a scale of 0.0 (clear) to 1.0 (ambiguous).

Query: "{query}"

Consider:
- Is the topic too broad? (e.g., "machine learning" vs "machine learning for medical diagnosis")
- Are there multiple interpretations? (e.g., "RAG systems" could mean architecture OR applications)
- Are key constraints missing? (e.g., "neural networks" - what domain? what year range?)

Respond ONLY with a number from 0.0 to 1.0, then on the next line, if ambiguous (>0.7), provide ONE clarifying question.

Format:
<score>
<question if needed>
"""
    
    response = await ai_client.generate_text(prompt, temperature=0.3, use_flash=True)
    lines = response.strip().split('\n')
    
    try:
        score = float(lines[0].strip())
        score = max(0.0, min(1.0, score))  # Clamp to 0-1
    except (ValueError, IndexError):
        score = 0.5  # Default to moderate ambiguity if parsing fails
    
    # Extract clarifying question if provided
    clarifying_question = None
    if len(lines) > 1 and score > 0.7:
        clarifying_question = '\n'.join(lines[1:]).strip()
    
    # If highly ambiguous, request clarification
    if score > 0.7 and clarifying_question:
        return {
            "query_ambiguity_score": score,
            "clarification_question": clarifying_question,
            "needs_clarification": True,
            "logs": [{
                "step": "clarifier",
                "source": "Clarifier",
                "message": f"❓ Query is ambiguous (score: {score:.2f}). Asking for clarification...",
                "status": "awaiting_user"
            }]
        }
    else:
        # Query is clear enough, proceed
        return {
            "query_ambiguity_score": score,
            "needs_clarification": False,
            "logs": [{
                "step": "clarifier",
                "source": "Clarifier",
                "message": f"✓ Query is clear (ambiguity score: {score:.2f})",
                "status": "completed"
            }]
        }


# ===== ROUTER NODE =====

async def router_node(state: ResearchState) -> Dict:
    """Classify user intent and route to appropriate subgraph"""
    import logging
    logger = logging.getLogger(__name__)
    
    query = state["query"]
    logger.info(f"Router analyzing query: '{query[:60]}...'")
    
    q_lower = query.lower().strip()
    is_factual_chat = _is_factual_chat_query(query)
    has_prior_research_context = _has_prior_research_context(state)

    # Respect earlier pre-classification when available.
    preclassified_intent = (state.get("intent_guarded") or state.get("intent_raw") or "").upper()
    if preclassified_intent in {"SEARCH", "DRAFT", "ANALYZE", "CHAT", "HELP", "DEEP_RESEARCH"}:
        if preclassified_intent == "DEEP_RESEARCH":
            intent = "SEARCH"
        elif preclassified_intent == "HELP":
            intent = "CHAT"
        elif preclassified_intent == "ANALYZE" and not any(k in q_lower for k in ["image", "figure", "data", "lab"]):
            # Keep conceptual "explain" requests out of lab-analysis path.
            intent = "CHAT"
        else:
            intent = preclassified_intent
        logger.info(f"Router using preclassified intent: {intent}")
    else:
        # FAST keyword-based classification (no LLM needed)
        greeting_terms = {
            "hi", "hello", "hey", "yo", "sup", "what's up", "whats up",
            "good morning", "good afternoon", "good evening", "hi there", "hello there",
        }

        if q_lower in greeting_terms:
            intent = "CHAT"
        elif "draft" in q_lower or "write" in q_lower or "outline" in q_lower or "compose" in q_lower:
            intent = "DRAFT"
        elif "analyze" in q_lower and ("image" in q_lower or "figure" in q_lower or "data" in q_lower or "lab" in q_lower):
            intent = "ANALYZE"
        else:
            # Default to SEARCH for research/knowledge queries.
            intent = "SEARCH"

    # For factual chat, reuse already-researched context via grounded response path.
    # This avoids generic answers and avoids launching a fresh search.
    if intent == "CHAT" and is_factual_chat and has_prior_research_context and settings.research_focused_mode:
        intent = "GROUNDED_CHAT"
    elif intent == "CHAT" and is_factual_chat and not has_prior_research_context and settings.research_focused_mode:
        if settings.auto_research_on_factual_queries:
            intent = "SEARCH"
            logger.info("Factual chat detected with no context; auto-routing to SEARCH for paper-grounded response.")
        else:
            logger.info("Factual chat detected but no prior research context; requiring evidence-first flow.")
    
    logger.info(f"Router classified intent as: {intent}")
    
    # Log step
    log_entry = {
        "step": "router",
        "source": "Router",
        "message": f"✓ Classified as {intent} intent",
        "status": "completed"
    }
    
    # Log agent activity
    agent_log = {
        "agent": "router",
        "action": "classify_intent",
        "result": intent,
        "timestamp": None
    }
    
    return {
        "intent": intent,
        "agent_history": [agent_log],
        "logs": [log_entry]
    }


# ===== SEARCH NODE (Discovery Loop) =====

async def search_node(state: ResearchState) -> Dict:
    """Search external APIs for papers with query analysis"""
    logger.info("=== ENTERING SEARCH NODE ===")
    
    from app.services.query_analyzer import query_analyzer
    from app.services.paper_search import search_all_sources
    
    query = state.get("refined_query") or state["query"]
    iteration = state.get("search_iteration", 0)
    
    logger.info(f"Search Node - Query: '{query}', Iteration: {iteration}")
    
    # Log step
    log_entry = {
        "step": "search",
        "source": "Search",
        "message": f"Analyzing query and searching (iteration {iteration + 1})...",
        "status": "processing"
    }
    
    try:
        # Step 1: Analyze query
        try:
            analysis = await query_analyzer.analyze_query(query)
            optimized_query = analysis.get("search_query", query)
            if not optimized_query or not optimized_query.strip():
                logger.warning("Optimized query was empty, falling back to original")
                optimized_query = query
            logger.info(f"Query optimized: '{query}' → '{optimized_query}'")
        except Exception as qa_err:
            logger.error(f"Query analysis failed: {qa_err}")
            optimized_query = query
            analysis = {"thought": "Query analysis failed, using original"}
            
        logger.info(f"=== EXECUTING SEARCH WITH QUERY: '{optimized_query}' ===")
        
        # Log query analysis
        thought_log = {
            "step": "search",
            "source": "QueryAnalyzer",
            "message": f"💡 Analyzed: {analysis.get('thought', 'Using raw query')}",
            "status": "completed"
        }
        
        # Step 2: Search all sources with optimized query
        found_papers = search_all_sources(optimized_query, max_results_per_source=5)
        
        # Step 3: If primary search fails, try expanded queries
        if len(found_papers) < 3 and analysis.get("expanded_queries"):
            for expanded_query in analysis["expanded_queries"][:2]:  # Try up to 2 expanded queries
                additional_papers = search_all_sources(expanded_query, max_results_per_source=3)
                found_papers.extend(additional_papers)
                
                if len(found_papers) >= 5:  # Stop if we have enough results
                    break
        
        # Deduplicate again after combining expanded results
        unique_papers = {}
        for paper in found_papers:
            title = paper.get('title') or ''
            title_key = title.lower().strip()
            if title_key and title_key not in unique_papers:
                unique_papers[title_key] = paper
        
        found_papers = list(unique_papers.values())[:10]  # Limit to 10 total
        
        # === AUTO-SAVE TO PROJECT LIBRARY (FIXED: Better Error Handling) ===
        project_id = state.get("project_id")
        saved_count = 0
        if project_id:
            try:
                db = next(get_db())
                for paper in found_papers:
                    # Check if already exists in this project
                    exists = db.query(LibraryItem).filter(
                        LibraryItem.project_id == project_id,
                        LibraryItem.title == paper["title"]
                    ).first()
                    
                    if not exists:
                        new_item = LibraryItem(
                            project_id=project_id,
                            title=paper["title"],
                            authors=paper.get("authors", []),
                            year=paper.get("year"),
                            abstract=paper.get("abstract") or paper.get("summary", ""),
                            url=paper.get("url") or paper.get("pdf_url"),
                            arxiv_id=paper.get("paperId") if "arxiv" in str(paper.get("paperId", "")).lower() else None,
                            is_selected_for_context=False  # Auto-added but not auto-selected for chat context
                        )
                        db.add(new_item)
                        saved_count += 1
                db.commit()
                db.close()
                logger.info(f"✓ Auto-saved {saved_count}/{len(found_papers)} new papers to library")
            except Exception as save_err:
                logger.error(f"✗ Error auto-saving papers to library: {save_err}", exc_info=True)
                # Non-blocking, but now properly logged
        
        # Check if no papers found and provide helpful feedback
        if len(found_papers) == 0:
            logger.warning(f"No papers found for query: '{query}'")
            return {
                "found_papers": [],
                "search_iteration": iteration + 1,
                "logs": [
                    log_entry,
                    thought_log,
                    {
                        "step": "search",
                        "source": "MultiSourceSearch",
                        "message": "⚠ No papers found. Try different keywords or broader terms.",
                        "status": "warning",
                        "metadata": {
                            "count": 0,
                            "optimized_query": optimized_query,
                            "suggestion": "Try rephrasing with different terminology or broader search terms"
                        }
                    }
                ]
            }
        
        return {
            "found_papers": found_papers,
            "search_iteration": iteration + 1,
            "logs": [
                log_entry,
                thought_log,
                {
                    "step": "search",
                    "source": "MultiSourceSearch",
                    "message": f"✓ Found {len(found_papers)} papers ({saved_count} new, {len(found_papers) - saved_count} existing)",
                    "status": "completed",
                    "metadata": {
                        "count": len(found_papers),
                        "saved_count": saved_count,
                        "optimized_query": optimized_query
                    }
                }
            ]
        }
    
    except Exception as e:
        return {
            "found_papers": [],
            "search_iteration": iteration + 1,
            "error": str(e),
            "logs": [
                {
                    "step": "search",
                    "source": "Search",
                    "message": f"✗ Search failed: {str(e)}",
                    "status": "error"
                }
            ]
        }


# ===== RANKER NODE (Discovery Loop Decision Point - OPTIMIZED: Batch Scoring) =====

async def ranker_node(state: ResearchState) -> Dict:
    """Score papers for relevance using AI - OPTIMIZED with batch scoring"""
    import time
    
    query = state["query"]
    found_papers = state["found_papers"]
    
    log_entry = {
        "step": "rank",
        "source": "Ranker",
        "message": f"Scoring {len(found_papers)} papers for relevance...",
        "status": "processing"
    }
    
    if not found_papers:
        return {
            "ranked_papers": [],
            "logs": [log_entry, {
                "step": "rank",
                "source": "Ranker",
                "message": "No papers to rank",
                "status": "completed"
            }]
        }
    
    ranked_papers = []
    start_time = time.time()
    
    # OPTIMIZATION: Batch score all papers in one LLM call (10x faster!)
    try:
        # Build single prompt with all papers
        papers_text = ""
        for i, paper in enumerate(found_papers, 1):
            title = paper.get("title", "Unknown")
            abstract = paper.get("abstract", paper.get("summary", "No abstract"))[:300]  # Limit length
            papers_text += f"{i}. TITLE: {title}\n   ABSTRACT: {abstract}\n\n"
        
        batch_prompt = f"""Rate the relevance of these {len(found_papers)} papers to the query on a scale of 0.0 to 1.0.

QUERY: "{query}"

PAPERS:
{papers_text}

Return ONLY the scores as a comma-separated list (e.g., "0.85, 0.72, 0.91, ...").
Return exactly {len(found_papers)} scores in the same order."""

        # Get all scores at once
        result = await ai_client.generate_text(batch_prompt, temperature=0.2, use_flash=True)
        
        # Parse scores
        score_strings = result.strip().split(',')
        scores = []
        for s in score_strings:
            try:
                score = float(s.strip())
                scores.append(max(0.0, min(1.0, score)))  # Clamp to [0, 1]
            except ValueError:
                scores.append(0.5)  # Default if parsing fails
        
        # Ensure we have enough scores (pad with 0.5 if needed)
        while len(scores) < len(found_papers):
            scores.append(0.5)
        
        # Assign scores to papers
        for paper, score in zip(found_papers, scores[:len(found_papers)]):
            paper["relevance_score"] = score
            ranked_papers.append(paper)
        
        elapsed = time.time() - start_time
        logger.info(f"⚡ Batch scored {len(ranked_papers)} papers in {elapsed:.2f}s")
        
    except Exception as batch_err:
        # Fallback to individual scoring if batch fails
        logger.warning(f"Batch scoring failed: {batch_err}. Falling back to individual scoring.")
        for paper in found_papers:
            score = await ai_client.score_paper_relevance(
                paper.get("title", ""),
                paper.get("abstract", paper.get("summary", "")),
                query
            )
            paper["relevance_score"] = score
            ranked_papers.append(paper)
    
    # Sort by relevance
    ranked_papers.sort(key=lambda p: p["relevance_score"], reverse=True)
    
    # Check if any paper meets threshold
    top_score = ranked_papers[0]["relevance_score"] if ranked_papers else 0.0
    meets_threshold = top_score >= settings.relevance_threshold
    
    return {
        "ranked_papers": ranked_papers,
        "logs": [
            log_entry,
            {
                "step": "rank",
                "source": "Ranker",
                "message": f"✓ Ranked {len(ranked_papers)} papers. Top score: {top_score:.2f}",
                "status": "completed",
                "metadata": {
                    "top_score": top_score,
                    "meets_threshold": meets_threshold
                }
            }
        ]
    }


# ===== RESEARCH COORDINATOR NODE (Intelligent Search Management) =====

async def research_coordinator_node(state: ResearchState) -> Dict:
    """Intelligent agent that evaluates search results and decides strategy"""
    from app.agents.specialists import get_research_coordinator_agent
    
    coordinator = get_research_coordinator_agent()
    
    query = state["query"]
    found_papers = state["found_papers"]
    ranked_papers = state["ranked_papers"]
    iteration = state.get("search_iteration", 0)
    
    log_entry = {
        "step": "research_coordinator",
        "source": "Research Coordinator",
        "message": "🧭 Evaluating search results and strategy...",
        "status": "processing"
    }
    
    # Get intelligent decision from coordinator agent
    evaluation = await coordinator.evaluate_search_results(
        query=query,
        found_papers=found_papers,
        ranked_papers=ranked_papers,
        iteration=iteration
    )
    
    decision = evaluation["decision"]
    reasoning = evaluation["reasoning"]
    suggestions = evaluation["suggestions"]
    
    # Build response log
    response_log = {
        "step": "research_coordinator",
        "source": "Research Coordinator",
        "message": f"🧭 Decision: {decision.upper()}",
        "status": "completed",
        "metadata": {
            "decision": decision,
            "reasoning": reasoning,
            "suggestions": suggestions,
            "quality_metrics": evaluation["quality_metrics"]
        }
    }
    
    return {
        "coordinator_decision": decision,
        "coordinator_reasoning": reasoning,
        "coordinator_suggestions": suggestions,
        "agent_history": [{
            "agent": "research_coordinator",
            "decision": decision,
            "reasoning": reasoning,
            "timestamp": None
        }],
        "logs": [log_entry, response_log]
    }


# ===== QUERY REFINER NODE (Discovery Loop Retry) =====

async def refine_query_node(state: ResearchState) -> Dict:
    """Refine search query based on coordinator's suggestions"""
    from app.agents.specialists import get_research_coordinator_agent
    
    coordinator = get_research_coordinator_agent()
    
    original_query = state["query"]
    iteration = state["search_iteration"]
    coordinator_suggestions = state.get("coordinator_suggestions", "")
    ranked_papers = state.get("ranked_papers", [])
    
    log_entry = {
        "step": "refine",
        "source": "QueryRefiner",
        "message": "Refining query based on coordinator guidance...",
        "status": "processing"
    }
    
    # Get refined query from coordinator
    reason = coordinator_suggestions if coordinator_suggestions else "Results not optimal"
    refined_query = await coordinator.suggest_query_refinement(
        original_query=original_query,
        search_results=ranked_papers,
        reason=reason
    )
    
    return {
        "refined_query": refined_query,
        "search_iteration": iteration + 1,
        "logs": [
            log_entry,
            {
                "step": "refine",
                "source": "QueryRefiner",
                "message": f"✓ Refined query: \"{refined_query}\"",
                "status": "completed"
            }
        ]
    }


# ===== OLD REFINE NODE (BACKUP - can be removed) =====

async def refine_query_node_old(state: ResearchState) -> Dict:
    """Refine search query based on failed results"""
    
    original_query = state["query"]
    iteration = state["search_iteration"]
    
    log_entry = {
        "step": "refine",
        "source": "QueryRefiner",
        "message": "Refining query for better results...",
        "status": "processing"
    }
    
    # Use AI to suggest refinement
    prompt = f"""The search query "{original_query}" returned no relevant papers.
Suggest a refined, more specific search query that might yield better results.
Return ONLY the refined query, nothing else."""
    
    refined = await ai_client.generate_text(prompt, temperature=0.7, use_flash=True)
    
    return {
        "refined_query": refined.strip(),
        "logs": [
            log_entry,
            {
                "step": "refine",
                "source": "QueryRefiner",
                "message": f"✓ Refined query: '{refined.strip()}'",
                "status": "completed"
            }
        ]
    }


# ===== LAB ANALYST NODE =====

async def lab_analyst_node(state: ResearchState) -> Dict:
    """Analyze lab assets using Gemini Vision"""
    
    asset_ids = state["lab_asset_ids"]
    project_id = state["project_id"]
    
    if not asset_ids:
        return {"logs": []}
    
    log_entry = {
        "step": "lab_analyst",
        "source": "LabAnalyst",
        "message": f"Analyzing {len(asset_ids)} lab assets...",
        "status": "processing"
    }
    
    descriptions = []
    
    # Get database session
    db = next(get_db())
    
    try:
        for asset_id in asset_ids:
            asset = db.query(LabAsset).filter(LabAsset.id == asset_id).first()
            
            if asset and asset.asset_type == "image":
                # Analyze with AI Vision
                if not asset.ai_description:
                    description = await ai_client.analyze_image(
                        asset.file_path,
                        prompt="Provide a detailed scientific description of this figure. Identify axes, trends, key data points, and any notable patterns."
                    )
                    
                    # Save description to DB
                    asset.ai_description = description
                    db.commit()
                    
                    descriptions.append(description)
                else:
                    descriptions.append(asset.ai_description)
        
        return {
            "lab_asset_descriptions": descriptions,
            "logs": [
                log_entry,
                {
                    "step": "lab_analyst",
                    "source": "LabAnalyst",
                    "message": f"✓ Analyzed {len(descriptions)} assets",
                    "status": "completed"
                }
            ]
        }
    
    finally:
        db.close()


# ===== WRITER NODE (Drafting Workflow) =====

async def writer_node(state: ResearchState) -> Dict:
    """Generate academic text with section-aware context blending"""
    
    from app.agents.prompts import format_section_prompt, get_context_weights
    from app.models.database import ResearchAsset
    from app.core.ai_client import ai_client
    
    query = state["query"]
    selected_paper_ids = state["selected_paper_ids"]
    research_asset_ids = state.get("research_asset_ids", [])
    
    current_draft = state.get("current_draft", {})
    factual_query = _is_factual_chat_query(query)
    has_research_context = _has_prior_research_context(state)

    # Lightweight conversational path for normal chat. Keep this separate from
    # manuscript drafting so casual conversation remains simple and direct.
    if (state.get("intent") or "").upper() == "CHAT":
        if (
            settings.research_focused_mode
            and factual_query
            and not has_research_context
            and not settings.auto_research_on_factual_queries
        ):
            return {
                "current_draft": {
                    "section": "Research Context Required",
                    "content": (
                        "I can answer this factually, but only with paper-grounded evidence.\n\n"
                        "No prior research context is available for this question yet.\n"
                        "Please do one of these first:\n"
                        "1. Select papers from your library, or\n"
                        "2. Ask me to search papers on this topic.\n\n"
                        "Once papers are available, I will answer with citations and references."
                    ),
                    "status": "research_context_required",
                },
                "logs": [{
                    "step": "writer",
                    "source": "Writer",
                    "message": "⚠ Factual query requires paper context before answering",
                    "status": "warning",
                }],
            }

        chat_prompt = (
            "You are ScholarFlow. Respond conversationally and concisely. "
            "If the user asks factual content that requires paper evidence and none was provided, "
            "ask them to run a paper search first instead of inventing facts.\n\n"
            f"User: {query}"
        )
        chat_text = await ai_client.generate_text(chat_prompt, temperature=0.4, use_flash=True)
        return {
            "current_draft": {
                "section": "Chat Response",
                "content": chat_text,
                "status": "chat",
            },
            "logs": [{
                "step": "writer",
                "source": "Writer",
                "message": "✓ Responded in basic conversation mode",
                "status": "completed",
            }],
        }
    
    # Check if we are in "Outline Generated" state -> Trigger Parallel Drafting
    if current_draft.get("status") == "outline_generated":
        sections_plan = current_draft.get("sections_plan", [])
        if not sections_plan:
            # Fallback if no plan
            current_draft["status"] = "drafting"
            return {"current_draft": current_draft} 
            
        log_entry = {
            "step": "writer",
            "source": "Writer",
            "message": f"🚀 Starting parallel drafting for {len(sections_plan)} sections...",
            "status": "processing"
        }
        
        # === PREPARE CONTEXT (Shared for all sections) ===
        # 1. Get literature context
        literature_context = ""
        if selected_paper_ids:
            project_id = state["project_id"]
            context_chunks = await vector_store.search_similar(
                project_id,
                query,
                paper_ids=selected_paper_ids,
                top_k=8 
            )
            literature_context = "\n\n".join(context_chunks) if context_chunks else ""
            
        # 2. Get research context
        research_context = ""
        db = next(get_db())
        try:
            if research_asset_ids:
                research_assets = db.query(ResearchAsset).filter(
                    ResearchAsset.id.in_(research_asset_ids)
                ).all()
                research_parts = []
                for asset in research_assets:
                    asset_info = f"**{asset.name}** ({asset.asset_type})"
                    if asset.description: asset_info += f": {asset.description}"
                    if asset.ai_analysis: asset_info += f"\nAnalysis: {asset.ai_analysis}"
                    research_parts.append(asset_info)
                research_context = "\n\n".join(research_parts)
        finally:
            db.close()
            
        # === PREPARE BATCH PROMPTS ===
        prompts = []
        section_titles = []
        
        for section in sections_plan:
            title = section.get("title", "Section")
            desc = section.get("description", "")
            
            research_weight, lit_weight = get_context_weights(title)
            
            section_prompt = format_section_prompt(
                title,
                query,
                literature_context=literature_context,
                research_context=research_context,
                allow_citations=bool(selected_paper_ids),
            )
            section_prompt += f"\n\nSpecific Focus for this part: {desc}"
            
            prompts.append(section_prompt)
            section_titles.append(title)
            
        # === EXECUTE PARALLEL GENERATION ===
        draft_results = await ai_client.generate_batch(
            prompts,
            temperature=0.7,
            mode="studio" 
        )
        
        # === ASSEMBLE RESULT ===
        final_content_parts = []
        logs = [log_entry]
        total_words = 0
        
        for i, text in enumerate(draft_results):
            title = section_titles[i]
            word_count = len(text.split())
            total_words += word_count
            
            final_content_parts.append(f"## {title}\n\n{text}")
            
            # Log each section completion for "Show Drafting Process"
            logs.append({
                "step": "writer",
                "source": "Writer",
                "message": f"✓ Drafted '{title}' ({word_count} words)",
                "status": "completed"
            })
            
        full_content = "\n\n".join(final_content_parts)
        
        return {
            "current_draft": {
                "section": "Full Manuscript",
                "content": full_content,
                "status": "pending_review"
            },
            "logs": logs
        }

    current_section = state.get("current_section", "general")
    lab_descriptions = state.get("lab_asset_descriptions", [])
    revision_count = state.get("revision_count", 0)
    critique = state.get("critique_feedback")
   
    log_entry = {
        "step": "writer",
        "source": "Writer",
        "message": f"Drafting {current_section} section (revision {revision_count})...",
        "status": "processing"
    }
    
    # === SECTION-AWARE CONTEXT GATHERING ===
    
    # 1. Get literature context from papers
    literature_context = ""
    if selected_paper_ids:
        project_id = state["project_id"]
        context_chunks = await vector_store.search_similar(
            project_id,
            query,
            paper_ids=selected_paper_ids,
            top_k=5
        )
        literature_context = "\n\n".join(context_chunks) if context_chunks else ""
    
    # 2. Get research context from student's assets
    research_context = ""
    db = next(get_db())
    try:
        if research_asset_ids:
            research_assets = db.query(ResearchAsset).filter(
                ResearchAsset.id.in_(research_asset_ids)
            ).all()
            
            research_parts = []
            for asset in research_assets:
                asset_info = f"**{asset.name}** ({asset.asset_type})"
                if asset.description:
                    asset_info += f": {asset.description}"
                if asset.methodology_note:
                    asset_info += f"\nMethodology: {asset.methodology_note}"
                if asset.ai_analysis:
                    asset_info += f"\nAnalysis: {asset.ai_analysis}"
                research_parts.append(asset_info)
            
            research_context = "\n\n".join(research_parts)
        
        # Fallback to legacy lab descriptions if no research assets
        if not research_context and lab_descriptions:
            research_context = "\n".join(lab_descriptions)
    
    finally:
        db.close()
    
    # === APPLY SECTION-AWARE WEIGHTING ===
    research_weight, lit_weight = get_context_weights(current_section)
    
    # Add weight indicators to help the LLM prioritize
    if research_weight > lit_weight:
        research_context = f"**PRIMARY FOCUS** (Student's Work):\n{research_context}" if research_context else ""
        literature_context = f"Supporting Context (Prior Work):\n{literature_context}" if literature_context else ""
    elif lit_weight > research_weight:
        literature_context = f"**PRIMARY FOCUS** (Prior Research):\n{literature_context}" if literature_context else ""
        research_context = f"Supporting Context (Student's Work):\n{research_context}" if research_context else ""
    
    # === BUILD SECTION-SPECIFIC PROMPT ===
    prompt = format_section_prompt(
        current_section,
        query,
        literature_context=literature_context or "None provided.",
        research_context=research_context or "None provided.",
        allow_citations=bool(selected_paper_ids),
    )
    
    # Add revision feedback if exists
    if critique:
        prompt += f"\n\n**REVISION FEEDBACK FROM REVIEWER:**\n{critique}\n\nPlease address this feedback."
    
    # === GENERATE TEXT ===
    # ALWAYS use studio mode for academic writing (original, plagiarism-free)
    # This ensures scholarflow-studio (3B) is used for drafting, not general model
    draft_text = await ai_client.generate_text(
        prompt, 
        temperature=0.7,
        mode="studio"  # Force studio mode for all drafting
    )
    
    # Add to memory
    memory = get_memory_agent()
    await memory.add_interaction("assistant", f"Generated {current_section} section", {
        "section": current_section,
        "word_count": len(draft_text.split())
    })
    
    return {
        "current_draft": {
            "section": current_section.title() if current_section else "General",
            "content": draft_text,
            "status": "pending_review"
        },
        "agent_history": [{
            "agent": "writer",
            "action": "generate_draft",
            "section": current_section,
            "timestamp": None
        }],
        "logs": [
            log_entry,
            {
                "step": "writer",
                "source": "Writer",
                "message": f"✓ Generated {len(draft_text.split())} words for {current_section}",
                "status": "completed",
                "metadata": {
                    "section": current_section,
                    "research_weight": research_weight,
                    "lit_weight": lit_weight
                }
            }
        ]
    }


# ===== REVIEWER NODE (Review Loop Decision Point) =====

async def reviewer_node(state: ResearchState) -> Dict:
    """Critique the draft for quality, tone, and citation accuracy"""
    
    draft = state["current_draft"]
    draft_content = draft.get("content", "")
    
    log_entry = {
        "step": "reviewer",
        "source": "Reviewer",
        "message": "Reviewing draft quality...",
        "status": "processing"
    }
    
    # Review prompt
    prompt = f"""You are a senior academic editor reviewing a draft.

DRAFT:
{draft_content}

Evaluate the draft on:
1. Academic tone and clarity
2. Citation usage (are claims supported?)
3. Flow and coherence
4. Potential hallucinations or unsupported claims

Respond with EITHER:
- "APPROVED" if the draft is good quality
- Or provide specific feedback for revision (2-3 sentences)
"""
    
    review_result = await ai_client.generate_text(prompt, temperature=0.3, use_flash=True)
    
    is_approved = "APPROVED" in review_result.upper()
    
    return {
        "critique_feedback": None if is_approved else review_result,
        "needs_revision": not is_approved,
        "revision_count": state.get("revision_count", 0) + (0 if is_approved else 1),
        "logs": [
            log_entry,
            {
                "step": "reviewer",
                "source": "Reviewer",
                "message": "✓ Approved" if is_approved else f"⚠ Needs revision: {review_result[:100]}...",
                "status": "completed" if is_approved else "warning"
            }
        ]
    }


# ===== ANALYZING PREPARATION NODE (Shows Thinking Status) =====

async def analyzing_preparation_node(state: ResearchState) -> Dict:
    """
    Show user that we're analyzing papers before the blocking LLM call.
    This creates a better UX by providing immediate feedback.
    """
    found_papers = state.get("found_papers", [])
    ranked_papers = state.get("ranked_papers", [])
    selected_paper_ids = state.get("selected_paper_ids", [])
    
    # Count papers we'll analyze
    paper_count = 0
    if selected_paper_ids:
        paper_count = len(selected_paper_ids)
        message = f"📚 Reading through {paper_count} papers from your library..."
    elif ranked_papers:
        paper_count = min(len(ranked_papers), 8)
        message = f"🔍 Analyzing top {paper_count} ranked papers..."
    elif found_papers:
        paper_count = min(len(found_papers), 8)
        message = f"🔍 Processing {paper_count} papers..."
    else:
        message = "🤔 Preparing to generate answer..."
    
    return {
        "logs": [{
            "step": "analyzing",
            "source": "ResearchAssistant",
            "message": message,
            "status": "processing"
        }]
    }


# ===== RAG RESPONSE NODE (Grounded Answer Generation) =====

async def rag_response_node(state: ResearchState) -> Dict:
    """
    Generate a response grounded in the found papers.
    
    CONTEXT SHELF PRIORITY:
    1. First check user's library (selected_paper_ids) - the "Context Shelf"
    2. Only use ArXiv/Scholar results if library has no relevant content
    """
    query = state["query"]
    project_id = state["project_id"]
    selected_paper_ids = state.get("selected_paper_ids", [])
    ranked_papers = state.get("ranked_papers", [])
    found_papers = state.get("found_papers", [])
    
    logs = []
    library_context = None
    library_papers_info = []
    
    # ===== STEP 0: RETRIEVE UNIFIED PROJECT MEMORY (Chat History) =====
    # TEMPORARILY DISABLED: Vector store memory retrieval was causing bottleneck
    memory_context = []
    # try:
    #     # Search for past relevant chat interactions (Unified Memory)
    #     chat_results = await vector_store.search_similar(
    #         project_id=project_id,
    #         query=query,
    #         top_k=3,  # Get top 3 conversaton snippets
    #         include_metadata=True
    #     )
    #     
    #     for res in chat_results:
    #         # Only include if it's a chat log
    #         if res.get("type") == "chat":
    #              memory_context.append(f"Previously discussed: {res.get('text')}")
    #              
    #     if memory_context:
    #         logs.append({
    #             "step": "rag_response",
    #             "source": "UnifiedMemory",
    #             "message": f"🧠 Recalled {len(memory_context)} relevant past interactions",
    #             "status": "completed"
    #         })
    # except Exception as mem_err:
    #     print(f"Memory retrieval warning: {mem_err}")

    # ===== STEP 1: CHECK CONTEXT SHELF FIRST =====
    if selected_paper_ids:
        log_entry = {
            "step": "rag_response",
            "source": "ContextShelf",
            "message": f"📚 Scanning your library ({len(selected_paper_ids)} papers)...",
            "status": "processing"
        }
        logs.append(log_entry)
        
        # Search user's library for relevant chunks WITH METADATA (Page numbers!)
        try:
            context_results = await vector_store.search_similar(
                project_id=project_id,
                query=query,
                paper_ids=selected_paper_ids,
                top_k=8,  # Increased context window
                include_metadata=True
            )
            
            if context_results:
                # Get unique paper IDs found
                found_paper_ids = list(set(r.get("paper_id") for r in context_results if r.get("paper_id")))
                
                # Fetch metadata for these papers
                from app.models.database import LibraryItem
                db = next(get_db())
                try:
                    db_papers = db.query(LibraryItem).filter(
                        LibraryItem.id.in_(found_paper_ids)
                    ).all()
                    paper_map = {p.id: p for p in db_papers}
                    
                    # Construct specific chunk objects for the LLM
                    for result in context_results:
                        p_id = result.get("paper_id")
                        paper = paper_map.get(p_id)
                        
                        if paper:
                            library_papers_info.append({
                                "title": paper.title,
                                "authors": paper.authors if isinstance(paper.authors, str) else ", ".join(paper.authors[:3]) if paper.authors else "Unknown",
                                "year": paper.year,
                                "text": result.get("text"),  # Use specific chunk text
                                "page_number": result.get("page_number"),  # Use page number!
                                "source": "User Library",
                                "pdf_path": paper.pdf_path,
                                "paperId": p_id
                            })
                            
                    library_context = True # Flag that we found stuff
                    
                finally:
                    db.close()
                
                logs.append({
                    "step": "rag_response",
                    "source": "ContextShelf",
                    "message": f"✓ Found {len(library_papers_info)} relevant passages in your library",
                    "status": "completed"
                })
        except Exception as e:
            logs.append({
                "step": "rag_response",
                "source": "ContextShelf",
                "message": f"⚠ Library search warning: {str(e)[:50]}",
                "status": "warning"
            })
    
    # ===== STEP 2: DECIDE DATA SOURCE (FIXED: Smart Fallback) =====
    if library_papers_info:
        # Use library papers first (priority)
        papers_to_use = library_papers_info
        source_type = "library"
        logs.append({
            "step": "rag_response",
            "source": "ResearchAssistant",
            "message": "📖 Answering from YOUR library papers",
            "status": "processing"
        })
    elif selected_paper_ids and not (ranked_papers or found_papers):
        # User selected papers, found nothing in library, AND no search was performed
        # Only then suggest they try searching externally
        return {
            "current_draft": {
                "section": "Response",
                "content": """I searched your selected papers but couldn't find specific information matching your question.

**Suggestions:**
1. Try rephrasing your question.
2. Ensure the relevant papers are selected in the sidebar.
3. If you want to search external papers (ArXiv), simply unselect your library papers or ask me to "Search external sources".""",
                "status": "no_context_found"
            },
            "logs": logs + [{
                "step": "rag_response",
                "source": "ResearchAssistant",
                "message": "⚠ No relevant info found in selected papers",
                "status": "warning"
            }]
        }
    else:
        # SMART FALLBACK: Use search results from ArXiv/Scholar
        # This happens if:
        # - No library papers selected, OR
        # - Library papers selected but didn't match (fallback to search results)
        papers_to_use = ranked_papers if ranked_papers else found_papers
        source_type = "external"
        
        # FORMAT EXTERNAL PAPERS: Ensure they have proper structure for RAG
        # External papers only have abstracts, not PDF chunks, but we can still use them
        formatted_external = []
        for paper in papers_to_use[:8]:  # Use top 8 papers
            formatted_external.append({
                "title": paper.get("title", "Unknown"),
                "authors": paper.get("authors", []),
                "year": paper.get("year"),
                "text": paper.get("abstract") or paper.get("summary", ""),  # Use abstract as text
                "source": paper.get("source", "ArXiv"),
                "url": paper.get("url") or paper.get("pdf_url"),
                "paperId": paper.get("paperId") or paper.get("id"),
                "relevance_score": paper.get("relevance_score", 0.0)
            })
        papers_to_use = formatted_external
        
        if papers_to_use:
            fallback_message = "🔍 Using papers from recent search" if selected_paper_ids else f"🔍 Using {len(papers_to_use)} papers from ArXiv/Scholar"
            logs.append({
                "step": "rag_response",
                "source": "ResearchAssistant",
                "message": fallback_message,
                "status": "processing"
            })
    
    # ===== STEP 3: CHECK IF WE HAVE ANY PAPERS =====
    if not papers_to_use:
        # No papers found - be honest about it
        return {
            "current_draft": {
                "section": "Response",
                "content": """I couldn't find any relevant papers for your query. 

**What you can do:**
1. **Upload papers** to your library for me to analyze
2. Try rephrasing your question with different keywords
3. Search for specific topics (e.g., "transformer attention mechanism" instead of "how transformers work")

Would you like me to try a different search?""",
                "status": "no_papers"
            },
            "logs": logs + [{
                "step": "rag_response",
                "source": "ResearchAssistant",
                "message": "⚠ No papers found to ground response",
                "status": "warning"
            }]
        }
    
    # Generate grounded response using the found papers
    # NOTE: Thinking status is now shown by analyzing_preparation_node
    try:
        result = await generate_grounded_response(
            query=query,
            papers=papers_to_use,
            ai_client=ai_client,
            prompt_type="research",
            research_context="\n\n".join(memory_context) if memory_context else None
        )
        
        response_content = result["content"]  # Formal written content
        narration = result["narration"]  # Avatar's spoken words
        thinking = result.get("thinking", "")  # Chain-of-Thought reasoning (optional)
        papers_used = result["papers_used"]

        if settings.research_focused_mode and settings.enforce_paper_citations and not papers_used:
            return {
                "current_draft": {
                    "section": "Evidence Verification Required",
                    "content": (
                        "I could not produce a citation-grounded answer from the currently available papers.\n\n"
                        "Please refine the question, select more relevant papers, or run a broader paper search.\n"
                        "I will answer once I can cite supporting sources."
                    ),
                    "status": "insufficient_citations",
                    "source_type": source_type,
                    "papers_used": [],
                    "total_papers": len(papers_to_use),
                    "source_verification_required": True,
                },
                "source_verification_required": True,
                "faithfulness_score": 0.0,
                "faithfulness_reason": "No citation evidence in generated answer.",
                "papers_to_save": [],
                "logs": logs + [{
                    "step": "rag_response",
                    "source": "ResearchAssistant",
                    "message": "⚠ Grounded answer rejected: no paper citations detected",
                    "status": "warning",
                    "metadata": {
                        "source_type": source_type,
                        "total_papers_found": result.get("total_papers_found", 0),
                    },
                }],
            }
        
        # Structured response formatting for better readability in the research chat UI.
        if source_type == "library":
            source_label = "Your Library"
        else:
            source_label = "Recent Search"

        evidence_lines = []
        for idx, used in enumerate(papers_used[:5], 1):
            title = used.get("title", "Untitled")
            source = used.get("source", "source unknown")
            evidence_lines.append(f"- [{idx}] **{title}** ({source})")

        evidence_block = "\n".join(evidence_lines) if evidence_lines else "- No specific citations were detected in this draft."

        response_with_source = (
            f"## Answer\n"
            f"{response_content}\n\n"
            f"## Evidence Used ({source_label})\n"
            f"{evidence_block}\n"
        )

        # Tier-2 hallucination guard: verify response faithfulness to retrieved chunks.
        from app.services.guardrails_service import check_response_faithfulness
        evidence_chunks = [p.get("text", "") for p in papers_to_use if p.get("text")]
        faithfulness = check_response_faithfulness(response_content, evidence_chunks)

        source_verification_required = faithfulness.status == "SOURCE_VERIFICATION"
        response_status = "grounded"
        if source_verification_required:
            response_status = "source_verification_required"
            logs.append({
                "step": "faithfulness_guard",
                "source": "GuardrailNode",
                "message": "⚠ Response flagged for source verification.",
                "status": "warning",
                "metadata": {
                    "decision_source": faithfulness.decision_source,
                    "reason": faithfulness.reason,
                    "confidence": faithfulness.confidence,
                },
            })
        
        return {
            "current_draft": {
                "section": "Research Response",
                "content": response_with_source,  # Written content
                "narration": narration,  # Spoken narration
                "thinking": thinking,  # Chain-of-Thought reasoning (optional)
                "status": response_status,
                "source_type": source_type,
                "papers_used": papers_used,
                "total_papers": len(papers_to_use),
                "source_verification_required": source_verification_required,
            },
            "source_verification_required": source_verification_required,
            "faithfulness_score": faithfulness.confidence,
            "faithfulness_reason": faithfulness.reason,
            "papers_to_save": papers_used if source_type == "external" else [],  # Only offer to save external papers
            "logs": logs + [{
                "step": "rag_response",
                "source": "ResearchAssistant",
                "message": f"✓ Generated response grounded in {len(papers_used)} papers ({source_type})",
                "status": "completed",
                "metadata": {
                    "papers_cited": len(papers_used),
                    "total_papers_found": result["total_papers_found"],
                    "source_type": source_type,
                    "source_verification_required": source_verification_required,
                }
            }]
        }
        
    except Exception as e:
        error_msg = str(e)
        logger_msg = f"✗ Response generation failed: {error_msg}"
        status = "error"
        
        # Friendly error for known limits
        if "Concurrent session limit" in error_msg or "429" in error_msg:
             error_msg = "I'm currently handling too many requests (Concurrent Session Limit). Please try again in a moment."
             logger_msg = "⚠ Concurrent session limit hit"
             status = "warning"
             
        return {
            "error": error_msg,
            "current_draft": {
                "section": "Response",
                "content": f"**System Notice:** {error_msg}\n\nI found relevant papers (see left panel), but could not generate a summary right now.",
                "status": "error"
            },
            "logs": logs + [{
                "step": "rag_response",
                "source": "ResearchAssistant",
                "message": logger_msg,
                "status": status
            }]
        }


async def deep_rag_pipeline_node(state: ResearchState) -> Dict:
    """
    Dedicated bypass path for QASPER-style evidence/method/data questions.
    This node skips general intent router and jumps straight into deep retrieval.
    """
    return {
        "deep_research_mode": True,
        "intent": "SEARCH",
        "logs": [{
            "step": "deep_rag_pipeline",
            "source": "DeepRAG",
            "message": "🔬 QASPER-style question detected. Triggering Deep RAG pipeline.",
            "status": "completed",
        }],
    }


# ============================================================
# PHASE 2 — CONTINUITY DETECTOR
# ============================================================

async def continuity_detector(state: ResearchState) -> Dict:
    """
    Classifies whether the current user turn is a follow-up to the previous
    conversation or a brand-new question.

    Sets:
        continuity_type: FOLLOW_UP_SAME_TOPIC | FOLLOW_UP_TOPIC_SHIFT | NEW_QUESTION
        continuity_confidence: 0.0-1.0
    """
    from app.agents.state import ResearchState  # avoid circular at top-level
    query = state.get("query", "")
    memory: list = state.get("conversation_memory", [])
    active_label = state.get("active_topic_label") or ""

    log_entry = {
        "step": "continuity_detector",
        "source": "ContinuityDetector",
        "message": "Detecting conversation continuity...",
        "status": "processing",
    }

    # ── Fast rules (no LLM needed) ───────────────────────────────
    FOLLOW_UP_SIGNALS = [
        "also", "additionally", "furthermore", "what about", "and",
        "can you also", "how about", "what if", "elaborate", "more detail",
        "expand on", "tell me more", "continue", "go on", "moreover",
        "in addition", "related to this", "regarding that", "based on",
        "following up", "as for", "yes", "ok", "sure", "great",
    ]
    NEW_SIGNALS = [
        "new topic", "something else", "change subject", "different question",
        "forget that", "let's talk about", "starting fresh", "by the way",
        "unrelated", "switch to", "now i want", "moving on",
    ]

    q_lower = query.lower().strip()
    is_short = len(q_lower.split()) <= 4

    hit_follow = any(q_lower.startswith(s) or f" {s} " in q_lower for s in FOLLOW_UP_SIGNALS)
    hit_new = any(s in q_lower for s in NEW_SIGNALS)
    no_history = len(memory) == 0

    if no_history or len(q_lower) < 8:
        ctype, conf = "NEW_QUESTION", 0.95
    elif hit_new:
        ctype, conf = "FOLLOW_UP_TOPIC_SHIFT", 0.85
    elif hit_follow or is_short:
        ctype, conf = "FOLLOW_UP_SAME_TOPIC", 0.80
    else:
        # Let the LLM decide for ambiguous cases
        try:
            last_turns = memory[-4:] if len(memory) >= 4 else memory
            history_text = "\n".join(
                f"{'User' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')[:200]}"
                for m in last_turns
            )
            active_hint = f"\nActive topic: {active_label}" if active_label else ""
            prompt = f"""Classify how the latest user message relates to the conversation so far.
Conversation history:
{history_text}{active_hint}

New message: "{query}"

Reply with ONE of:
FOLLOW_UP_SAME_TOPIC   — continues the same topic
FOLLOW_UP_TOPIC_SHIFT  — related but shifting direction
NEW_QUESTION           — completely new topic

Then on the same line add a confidence 0.0-1.0 separated by a space.
Example: FOLLOW_UP_SAME_TOPIC 0.9
"""
            response = await ai_client.generate_text(prompt, temperature=0.2, use_flash=True)
            parts = response.strip().split()
            ctype = parts[0].upper() if parts else "NEW_QUESTION"
            conf = float(parts[1]) if len(parts) > 1 else 0.7
            if ctype not in {"FOLLOW_UP_SAME_TOPIC", "FOLLOW_UP_TOPIC_SHIFT", "NEW_QUESTION"}:
                ctype, conf = "NEW_QUESTION", 0.6
        except Exception as e:
            logger.warning(f"Continuity LLM fallback failed: {e}")
            ctype, conf = "NEW_QUESTION", 0.5

    logger.info(f"🔍 Continuity: {ctype} (conf={conf:.2f})")
    return {
        "continuity_type": ctype,
        "continuity_confidence": conf,
        "logs": [log_entry, {
            "step": "continuity_detector",
            "source": "ContinuityDetector",
            "message": f"✓ Turn classified as {ctype} (confidence: {conf:.0%})",
            "status": "completed",
        }],
    }


# ============================================================
# PHASE 2 — TOPIC QUEUE MANAGER
# ============================================================

import uuid as _uuid

async def topic_queue_manager(state: ResearchState) -> Dict:
    """
    Manages up to two concurrent topic slots.
    - active_topic   — current topic being handled
    - queued_topic   — paused previous topic

    Rules:
    • NEW_QUESTION  → active becomes queued; new topic becomes active
    • FOLLOW_UP_SAME_TOPIC → no change
    • FOLLOW_UP_TOPIC_SHIFT → update active_topic_label, keep queued
    • If queue is full on NEW_QUESTION, replace queued (lower-priority)
    """
    query = state.get("query", "")
    ctype = state.get("continuity_type", "NEW_QUESTION")
    active_id = state.get("active_topic_id")
    active_label = state.get("active_topic_label")
    queued_id = state.get("queued_topic_id")
    queued_label = state.get("queued_topic_label")

    log_entry = {
        "step": "topic_queue_manager",
        "source": "TopicQueueManager",
        "message": "Managing topic slots...",
        "status": "processing",
    }

    topic_label = query[:80] if len(query) > 80 else query
    new_id = str(_uuid.uuid4())[:8]
    reason = ""

    if ctype == "FOLLOW_UP_SAME_TOPIC":
        # No change needed
        reason = "Continuing same topic."
        result = {
            "active_topic_id": active_id,
            "active_topic_label": active_label,
            "queued_topic_id": queued_id,
            "queued_topic_label": queued_label,
            "topic_queue_reason": reason,
        }
    elif ctype == "FOLLOW_UP_TOPIC_SHIFT":
        # Refine active topic label
        reason = "Topic shifted — updating active topic."
        result = {
            "active_topic_id": active_id or new_id,
            "active_topic_label": topic_label,
            "queued_topic_id": queued_id,
            "queued_topic_label": queued_label,
            "topic_queue_reason": reason,
        }
    else:  # NEW_QUESTION
        # Move current active to queued slot (overwriting stale queued)
        reason = f"New topic. Queued previous: '{active_label or 'none'}'."
        result = {
            "active_topic_id": new_id,
            "active_topic_label": topic_label,
            "queued_topic_id": active_id,
            "queued_topic_label": active_label,
            "topic_queue_reason": reason,
        }

    logger.info(f"📋 TopicQueue: active='{result['active_topic_label']}' queued='{result['queued_topic_label']}' — {reason}")
    return {
        **result,
        "logs": [log_entry, {
            "step": "topic_queue_manager",
            "source": "TopicQueueManager",
            "message": f"✓ {reason}",
            "status": "completed",
        }],
    }


# ============================================================
# PHASE 2 — INTERRUPT HANDLER
# ============================================================

async def interrupt_handler(state: ResearchState) -> Dict:
    """
    Detects explicit/implicit user interrupts (e.g. 'stop', 'wait', topic pivot)
    and safely saves state for resume.

    Sets:
        interrupted: bool
        interrupt_reason: str
        interrupt_saved_state: dict snapshot
        resume_token: str
        workflow_state: 'paused' if interrupted, else unchanged
    """
    query = state.get("query", "").lower().strip()

    INTERRUPT_SIGNALS = [
        "stop", "wait", "pause", "hold on", "cancel", "nevermind", "never mind",
        "abort", "forget it", "let's stop", "drop that", "set aside", "put that on hold",
        "i changed my mind",
    ]

    is_interrupt = any(sig in query for sig in INTERRUPT_SIGNALS)

    log_entry = {
        "step": "interrupt_handler",
        "source": "InterruptHandler",
        "message": "Checking for interrupt signals...",
        "status": "processing",
    }

    if not is_interrupt:
        return {"interrupted": False, "logs": [log_entry, {
            "step": "interrupt_handler", "source": "InterruptHandler",
            "message": "No interrupt detected.", "status": "completed",
        }]}

    import json as _json
    # Save a lightweight snapshot (not messages, which can be large)
    snapshot = {
        "query": state.get("query"),
        "intent": state.get("intent"),
        "current_draft": state.get("current_draft"),
        "active_topic_id": state.get("active_topic_id"),
        "active_topic_label": state.get("active_topic_label"),
        "search_iteration": state.get("search_iteration"),
        "workflow_state": state.get("workflow_state"),
    }
    resume_token = str(_uuid.uuid4())

    logger.info(f"🛑 Interrupt detected (token={resume_token}): '{query}'")
    return {
        "interrupted": True,
        "interrupt_reason": query,
        "interrupt_saved_state": snapshot,
        "resume_token": resume_token,
        "workflow_state": "paused",
        "logs": [log_entry, {
            "step": "interrupt_handler",
            "source": "InterruptHandler",
            "message": f"⏸ Work paused. Resume token: {resume_token}",
            "status": "completed",
        }],
    }


# ============================================================
# PHASE 3 — INTENT CLASSIFIER (FAST)
# ============================================================

_INTENT_KEYWORD_MAP = {
    "SEARCH": [
        "find", "search", "look up", "look for", "papers on", "articles about",
        "literature on", "studies on", "research on", "what are some papers",
    ],
    "DRAFT": [
        "write", "draft", "compose", "generate section", "create introduction",
        "write abstract", "add paragraph", "revise", "edit", "rewrite",
    ],
    "ANALYZE": [
        "analyze", "analyse", "evaluate", "assess", "explain", "compare",
        "contrast", "critique", "review paper", "understand methodology",
    ],
    "SYNTHESIZE": [
        "synthesize", "combine findings", "meta-analysis", "across papers",
        "overall trend", "what do all", "what do the papers say",
    ],
    "CITATION": [
        "cite", "citation", "reference", "bibliography", "citing", "citation format",
        "add reference", "in-text citation",
    ],
    "HELP": [
        "help", "how do i", "what can you", "tutorial", "guide",
        "what is scholarflow", "features", "capabilities",
    ],
}


async def intent_classifier_fast(state: ResearchState) -> Dict:
    """
    Lightweight rule-based intent classifier that runs before the guardrail.
    Avoids an LLM call for clearly identifiable intents.

    Sets:
        intent_raw: str   — classified intent (pre-guardrail)
        intent_confidence: float
    """
    query = state.get("query", "").lower()
    existing_intent = state.get("intent")

    log_entry = {
        "step": "intent_classifier_fast",
        "source": "IntentClassifier",
        "message": "Running fast intent classification...",
        "status": "processing",
    }

    best_intent = existing_intent or "CHAT"
    best_conf = 0.4  # default if no keyword match

    scores: Dict[str, int] = {}
    for intent, keywords in _INTENT_KEYWORD_MAP.items():
        hits = sum(1 for kw in keywords if kw in query)
        if hits > 0:
            scores[intent] = hits

    if scores:
        best_intent = max(scores, key=lambda k: scores[k])
        # Confidence: normalize hits against max possible
        max_kw = len(_INTENT_KEYWORD_MAP.get(best_intent, []))
        best_conf = min(0.95, 0.55 + (scores[best_intent] / max_kw) * 0.4)

    logger.info(f"🎯 FastIntent: {best_intent} ({best_conf:.2f})")
    return {
        "intent_raw": best_intent,
        "intent_confidence": best_conf,
        "logs": [log_entry, {
            "step": "intent_classifier_fast",
            "source": "IntentClassifier",
            "message": f"✓ Intent classified as {best_intent} ({best_conf:.0%} confidence)",
            "status": "completed",
        }],
    }


# ============================================================
# PHASE 3 — INTENT GUARDRAIL NODE
# ============================================================

async def intent_guardrail_node(state: ResearchState) -> Dict:
    """
    Runs intent through the guardrails service.
    Adds guardrail verdict to state and logs.

    Sets:
        intent_guarded: str
        intent_guardrail_status: ALLOW | BLOCK | CLARIFY
        intent_guardrail_reason: str
        decision_source: RULE | NEMO | LLM
    """
    from app.services.guardrails_service import GuardrailContext, check_intent_guardrails

    ctx = GuardrailContext(
        query=state.get("query", ""),
        intent_raw=state.get("intent_raw"),
        conversation_history=state.get("conversation_memory", []),
        project_id=state.get("project_id"),
        session_id=state.get("session_id"),
    )

    log_entry = {
        "step": "intent_guardrail",
        "source": "GuardrailNode",
        "message": "Running intent guardrail check...",
        "status": "processing",
    }

    decision = check_intent_guardrails(ctx)

    emoji = {"ALLOW": "✅", "BLOCK": "🚫", "CLARIFY": "❓"}.get(decision.status, "🔍")
    logger.info(
        f"{emoji} Guardrail: {decision.status} via {decision.decision_source} — {decision.reason}"
    )

    # If allowed, propagate guarded intent as primary intent for routing
    updates: Dict = {
        "intent_guardrail_status": decision.status,
        "intent_guardrail_reason": decision.reason,
        "decision_source": decision.decision_source,
        "logs": [log_entry, {
            "step": "intent_guardrail",
            "source": "GuardrailNode",
            "message": f"{emoji} Guardrail: {decision.status} — {decision.reason}",
            "status": "completed",
        }],
    }

    if decision.intent_guarded:
        updates["intent_guarded"] = decision.intent_guarded
        # Promote to primary intent if not already set or if guardrail refined it
        if not state.get("intent") or decision.decision_source == "NEMO":
            updates["intent"] = decision.intent_guarded

    if decision.status == "BLOCK":
        updates["workflow_state"] = "blocked"
        updates["current_draft"] = {
            "section": "Guardrail Response",
            "content": (
                "⚠️ **This request cannot be processed.**\n\n"
                f"Reason: {decision.reason}\n\n"
                "ScholarFlow is designed to assist with academic research and writing. "
                "Please rephrase your question within those boundaries."
            ),
            "status": "blocked",
        }
    elif decision.status == "CLARIFY":
        updates["needs_clarification"] = True
        updates["clarification_question"] = decision.reason

    return updates


# ============================================================
# PHASE 3 — LLM NECESSITY GATE
# ============================================================

_DETERMINISTIC_INTENTS = {"HELP"}
_DETERMINISTIC_QUERY_PATTERNS = [
    r"^\s*hi\s*$",
    r"^\s*hello\s*$",
    r"^\s*hey\s*$",
    r"^\s*hi there\s*$",
    r"^\s*hello there\s*$",
    r"^\s*good (morning|afternoon|evening)\s*$",
    r"^\s*what'?s up\s*$",
    r"\bwhat is your name\b",
    r"\bwho are you\b",
    r"\bwhat can you do\b",
    r"\bhelp\b$",
    r"\bstatus\b",
    r"\bqueue\b",
    r"\bactive topic\b",
    r"\bpaused\b",
    r"\bresume\b",
    r"\bcancel\b",
]


async def llm_necessity_gate(state: ResearchState) -> Dict:
    """
    Decides whether the request requires a full LLM call or can be handled
    deterministically.

    Sets:
        needs_llm: bool
        llm_gate_reason: str
    """
    import re as _re

    intent_guarded = state.get("intent_guarded") or state.get("intent_raw") or "CHAT"
    query = state.get("query", "").lower().strip()
    guardrail_status = state.get("intent_guardrail_status", "ALLOW")

    log_entry = {
        "step": "llm_necessity_gate",
        "source": "LLMGate",
        "message": "Evaluating LLM necessity...",
        "status": "processing",
    }

    # Blocked queries never need LLM
    if guardrail_status == "BLOCK":
        return {
            "needs_llm": False,
            "llm_gate_reason": "Blocked by guardrail — no LLM needed.",
            "logs": [log_entry, {"step": "llm_necessity_gate", "source": "LLMGate",
                                  "message": "⚡ LLM skipped (blocked query)", "status": "completed"}],
        }

    # Help/command intents are deterministic
    if intent_guarded in _DETERMINISTIC_INTENTS:
        return {
            "needs_llm": False,
            "llm_gate_reason": f"Intent '{intent_guarded}' is handled deterministically.",
            "logs": [log_entry, {"step": "llm_necessity_gate", "source": "LLMGate",
                                  "message": f"⚡ LLM skipped (deterministic intent: {intent_guarded})", "status": "completed"}],
        }

    # Short deterministic pattern match
    for pat in _DETERMINISTIC_QUERY_PATTERNS:
        if _re.search(pat, query, _re.IGNORECASE):
            return {
                "needs_llm": False,
                "llm_gate_reason": f"Query matches deterministic pattern: {pat}",
                "logs": [log_entry, {"step": "llm_necessity_gate", "source": "LLMGate",
                                      "message": "⚡ LLM skipped (pattern match)", "status": "completed"}],
            }

    # All other intents require LLM
    logger.info(f"🧠 LLM required for intent={intent_guarded}")
    return {
        "needs_llm": True,
        "llm_gate_reason": f"Intent '{intent_guarded}' requires LLM reasoning.",
        "logs": [log_entry, {"step": "llm_necessity_gate", "source": "LLMGate",
                              "message": f"🧠 LLM required (intent: {intent_guarded})", "status": "completed"}],
    }


# ============================================================
# PHASE 3 — DETERMINISTIC HANDLER
# ============================================================

_HELP_RESPONSE = """
# ScholarFlow AI Assistant

I can help you with:
- 🔍 **Search** — Find academic papers on any topic
- ✍️ **Draft** — Write and refine manuscript sections
- 📊 **Analyze** — Deep-dive into paper methodology and findings
- 🔗 **Cite** — Manage references and generate bibliographies
- 🧠 **Synthesize** — Compare and combine insights across multiple papers

Type your question or use the sidebar to get started!
""".strip()


async def deterministic_handler(state: ResearchState) -> Dict:
    """
    Returns fast responses without LLM invocation for simple/status queries.
    """
    query = state.get("query", "").lower().strip()
    active_label = state.get("active_topic_label") or "None"
    queued_label = state.get("queued_topic_label") or "None"
    intent_guarded = state.get("intent_guarded") or "HELP"

    log_entry = {
        "step": "deterministic_handler",
        "source": "DeterministicHandler",
        "message": "Generating deterministic response...",
        "status": "processing",
    }

    # Queue/topic status query
    if "queue" in query or "topic" in query or "active" in query or "paused" in query:
        response = (
            f"**Active topic:** {active_label}\n"
            f"**Queued topic:** {queued_label}\n\n"
            "Say **'continue previous'** to resume the queued topic, or ask a new question."
        )
    elif "resume" in query or "continue previous" in query:
        if state.get("queued_topic_id"):
            response = (
                f"Resuming your previous topic: **{queued_label}**\n\n"
                "Starting where you left off..."
            )
        else:
            response = "No queued topic to resume. You can start a new question."
    else:
        response = _HELP_RESPONSE

    logger.info(f"⚡ Deterministic response for intent={intent_guarded}")
    return {
        "current_draft": {"section": "Response", "content": response, "status": "complete"},
        "workflow_state": "complete",
        "logs": [log_entry, {
            "step": "deterministic_handler",
            "source": "DeterministicHandler",
            "message": "✓ Deterministic response sent.",
            "status": "completed",
        }],
    }


# ============================================================
# PHASE 4 — PLANNER REVIEWER NODE
# ============================================================

import json as _json

MAX_PLANNER_REVIEW_ITERATIONS = 3

async def planner_reviewer_node(state: ResearchState) -> Dict:
    """
    Reviews the planner's output JSON for completeness, safety, and feasibility.
    If issues are found (and max iterations not exceeded), requests revision.

    Sets:
        planner_review_status: APPROVED | REVISE
        planner_review_feedback: str
        planner_review_iterations: int (incremented each call)
    """
    current_draft = state.get("current_draft", {})
    plan_raw = current_draft.get("plan") or current_draft.get("content", "")
    iterations = state.get("planner_review_iterations", 0)

    log_entry = {
        "step": "planner_reviewer",
        "source": "PlannerReviewer",
        "message": f"Reviewing planner output (iteration {iterations + 1})...",
        "status": "processing",
    }

    if current_draft.get("status") == "outline_generated" and current_draft.get("sections_plan"):
        return {
            "planner_review_status": "APPROVED",
            "planner_review_feedback": "Structured outline generated successfully.",
            "planner_review_iterations": iterations + 1,
            "logs": [log_entry, {
                "step": "planner_reviewer",
                "source": "PlannerReviewer",
                "message": "Outline-based plan approved.",
                "status": "completed",
            }],
        }

    # Guard: max iterations reached → force approve to avoid infinite loop
    if iterations >= MAX_PLANNER_REVIEW_ITERATIONS:
        logger.warning(f"⚠️ PlannerReviewer: max iterations ({MAX_PLANNER_REVIEW_ITERATIONS}) reached — force APPROVED")
        return {
            "planner_review_status": "APPROVED",
            "planner_review_feedback": "Max review iterations reached — executing plan as-is.",
            "planner_review_iterations": iterations + 1,
            "logs": [log_entry, {
                "step": "planner_reviewer", "source": "PlannerReviewer",
                "message": "⚠️ Max iterations — plan force-approved.", "status": "completed",
            }],
        }

    # ── Parse plan ──────────────────────────────────────────────────────────
    plan: dict = {}
    if isinstance(plan_raw, dict):
        plan = plan_raw
    else:
        # Try to extract JSON from string
        try:
            match = __import__("re").search(r"\{.*\}", str(plan_raw), __import__("re").DOTALL)
            if match:
                plan = _json.loads(match.group(0))
        except Exception:
            pass

    # ── Deterministic checks ────────────────────────────────────────────────
    issues = []

    if not plan.get("goal"):
        issues.append("Missing 'goal' in plan.")
    steps = plan.get("steps", [])
    if not steps:
        issues.append("Plan has no steps.")
    elif len(steps) > 20:
        issues.append("Plan has too many steps (>20). Reduce scope.")

    required_tools = plan.get("required_tools", [])
    if not required_tools:
        issues.append("No required_tools specified.")

    success_criteria = plan.get("success_criteria", [])
    if not success_criteria:
        issues.append("No success_criteria defined.")

    # Check for circular references (same step label appearing twice)
    step_labels = [str(s.get("action", s)).lower() for s in steps if isinstance(s, dict)]
    seen: set = set()
    for label in step_labels:
        if label in seen:
            issues.append(f"Duplicate step detected: '{label}'.")
            break
        seen.add(label)

    if issues:
        feedback = "Planner output needs revision:\n• " + "\n• ".join(issues)
        logger.info(f"🔁 PlannerReviewer REVISE: {issues}")
        return {
            "planner_review_status": "REVISE",
            "planner_review_feedback": feedback,
            "planner_review_iterations": iterations + 1,
            "logs": [log_entry, {
                "step": "planner_reviewer", "source": "PlannerReviewer",
                "message": f"🔁 Plan revision requested: {'; '.join(issues)}", "status": "completed",
            }],
        }

    logger.info("✅ PlannerReviewer: plan APPROVED")
    return {
        "planner_review_status": "APPROVED",
        "planner_review_feedback": "Plan meets all quality criteria.",
        "planner_review_iterations": iterations + 1,
        "logs": [log_entry, {
            "step": "planner_reviewer", "source": "PlannerReviewer",
            "message": "✅ Plan approved.", "status": "completed",
        }],
    }

