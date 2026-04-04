"""Agent coordination API endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

from app.models.database import get_db, Project, LibraryItem
from app.agents.specialists import (
    get_proactive_agent,
    get_memory_agent,
    get_citation_agent,
    get_synthesis_agent
)
from app.agents.state import create_initial_state, ResearchState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class ProactiveSuggestionsRequest(BaseModel):
    """Request for proactive suggestions"""
    project_id: str
    current_draft: Optional[Dict] = None
    selected_paper_ids: List[str] = []


class ProactiveSuggestionsResponse(BaseModel):
    """Proactive suggestions from the agent"""
    suggestions: List[Dict]
    quality_feedback: Optional[Dict] = None


class MemoryInsightsRequest(BaseModel):
    """Request for research insights from memory"""
    project_id: str


class MemoryInsightsResponse(BaseModel):
    """Research insights extracted from conversation history"""
    key_findings: List[str]
    methodologies: List[str]
    gaps_identified: List[str]
    conversation_summary: str


class CitationCheckRequest(BaseModel):
    """Request to check citations in draft"""
    draft_text: str
    project_id: str
    citation_style: str = "IEEE"


class CitationCheckResponse(BaseModel):
    """Citation analysis results"""
    total_citations: int
    suggestions: List[Dict]
    bibliography: str


class SynthesisRequest(BaseModel):
    """Request for multi-paper synthesis"""
    project_id: str
    focus_area: Optional[str] = None


class SynthesisResponse(BaseModel):
    """Synthesis of papers"""
    synthesis_summary: str
    comparative_analysis: Optional[Dict] = None
    paper_count: int


@router.post("/proactive-suggestions", response_model=ProactiveSuggestionsResponse)
async def get_proactive_suggestions(
    request: ProactiveSuggestionsRequest,
    db: Session = Depends(get_db)
):
    """Get proactive suggestions for next actions"""
    
    proactive = get_proactive_agent()
    
    # Build state from request
    state: ResearchState = {
        "project_id": request.project_id,
        "query": "",
        "selected_paper_ids": request.selected_paper_ids,
        "current_draft": request.current_draft or {},
        "ranked_papers": [],
        "messages": [],
        "found_papers": [],
        "search_iteration": 0,
        "refined_query": None,
        "lab_asset_ids": [],
        "lab_asset_descriptions": [],
        "research_asset_ids": [],
        "research_asset_descriptions": [],
        "current_section": None,
        "critique_feedback": None,
        "revision_count": 0,
        "needs_revision": False,
        "intent": None,
        "logs": [],
        "papers_to_save": [],
        "error": None,
        "active_agent": "proactive",
        "agent_history": [],
        "supervisor_decision": None,
        "conversation_memory": [],
        "research_insights": {"key_findings": [], "methodologies": [], "gaps_identified": []},
        "user_preferences": {"citation_style": "IEEE", "writing_tone": "academic"},
        "citations_used": {},
        "bibliography": [],
        "citation_suggestions": [],
        "next_actions": [],
        "quality_feedback": None,
        "synthesis_summary": None,
        "comparative_analysis": None
    }
    
    # Get papers info for quality analysis
    if request.selected_paper_ids:
        papers = db.query(LibraryItem).filter(
            LibraryItem.id.in_(request.selected_paper_ids)
        ).all()
        state["ranked_papers"] = [
            {
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "abstract": p.abstract
            }
            for p in papers
        ]
    
    # Generate suggestions
    suggestions = await proactive.suggest_next_actions(state)
    
    # Analyze draft quality if available
    quality_feedback = None
    if request.current_draft and request.current_draft.get("content"):
        quality_feedback = await proactive.analyze_draft_quality(
            request.current_draft["content"],
            state["ranked_papers"]
        )
    
    return ProactiveSuggestionsResponse(
        suggestions=suggestions,
        quality_feedback=quality_feedback
    )


@router.post("/memory-insights", response_model=MemoryInsightsResponse)
async def get_memory_insights(
    request: MemoryInsightsRequest,
    db: Session = Depends(get_db)
):
    """Get research insights from conversation memory"""
    
    memory = get_memory_agent()
    
    # Extract insights
    insights = await memory.extract_research_insights()
    
    # Generate summary
    conversation_summary = ""
    if memory.conversation_history:
        recent = memory.conversation_history[-10:]
        conversation_summary = f"Recent activity: {len(recent)} interactions"
    
    return MemoryInsightsResponse(
        key_findings=insights.get("key_findings", []),
        methodologies=insights.get("methodologies", []),
        gaps_identified=insights.get("gaps_identified", []),
        conversation_summary=conversation_summary
    )


@router.post("/citation-check", response_model=CitationCheckResponse)
async def check_citations(
    request: CitationCheckRequest,
    db: Session = Depends(get_db)
):
    """Check citations in draft and provide suggestions"""
    
    citation_agent = get_citation_agent()
    citation_agent.citation_style = request.citation_style
    
    # Get available papers
    project = db.query(Project).filter(Project.id == request.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    papers = db.query(LibraryItem).filter(
        LibraryItem.project_id == request.project_id
    ).all()
    
    papers_list = [
        {
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "abstract": p.abstract
        }
        for p in papers
    ]
    
    # Count existing citations
    total_citations = request.draft_text.count("[")
    
    # Get suggestions
    suggestions = await citation_agent.suggest_citations(
        request.draft_text,
        papers_list
    )
    
    # Generate bibliography
    bibliography = await citation_agent.generate_bibliography(papers_list[:10])
    
    return CitationCheckResponse(
        total_citations=total_citations,
        suggestions=suggestions,
        bibliography=bibliography
    )


@router.post("/synthesis", response_model=SynthesisResponse)
async def synthesize_papers(
    request: SynthesisRequest,
    db: Session = Depends(get_db)
):
    """Generate synthesis of papers in project"""
    
    synthesis_agent = get_synthesis_agent()
    
    # Get papers
    papers = db.query(LibraryItem).filter(
        LibraryItem.project_id == request.project_id
    ).all()
    
    if not papers:
        raise HTTPException(status_code=404, detail="No papers found in project")
    
    papers_list = [
        {
            "id": p.id,
            "title": p.title,
            "authors": p.authors,
            "year": p.year,
            "abstract": p.abstract
        }
        for p in papers
    ]
    
    # Generate synthesis
    synthesis_text = await synthesis_agent.synthesize_papers(
        papers_list,
        focus_area=request.focus_area
    )
    
    # Generate comparison if multiple papers
    comparative_analysis = None
    if len(papers_list) >= 2:
        comparative_analysis = await synthesis_agent.compare_papers(papers_list)
    
    return SynthesisResponse(
        synthesis_summary=synthesis_text,
        comparative_analysis=comparative_analysis,
        paper_count=len(papers_list)
    )
