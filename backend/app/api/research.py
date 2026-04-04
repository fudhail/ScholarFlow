"""Research mode endpoints for question answering with RAG"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import asyncio
import logging
import uuid

from app.models.database import get_db, Project, LibraryItem, Draft, ResearchAsset
from app.models.schemas import (
    OutlineRequest,
    OutlineResponse,
    OutlineSection,
    SaveDraftRequest,
    DraftResponse,
    ResearchAssetResponse,
    ResearchAssetType,
)
from app.services.query_analyzer import query_analyzer
from app.services.paper_search import search_all_sources
from app.core.ai_client import ai_client
from app.services.answer_generator import answer_generator
from app.services.research_asset_service import research_asset_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


def _normalize_heading(title: str) -> str:
    return " ".join(
        ''.join(ch.lower() if ch.isalnum() or ch.isspace() else ' ' for ch in (title or '')).split()
    )


def _canonicalize_outline_title(title: str) -> str:
    t = _normalize_heading(title)
    if t in {"introduction", "background", "related work", "literature review"}:
        return "Introduction"
    if t in {"methods", "methodology", "materials and methods", "approach", "proposed method"}:
        return "Methodology"
    if t in {"results", "experiments", "experimental results", "evaluation"}:
        return "Results"
    if t in {"discussion", "analysis", "interpretation"}:
        return "Discussion"
    if t in {"conclusion", "conclusions", "future work"}:
        return "Conclusion"
    if t in {"references", "bibliography", "works cited", "sources"}:
        return "References"
    return (title or "Section").strip()


def _order_outline_sections(sections: List[OutlineSection]) -> List[OutlineSection]:
    order = {
        "Introduction": 0,
        "Methodology": 1,
        "Results": 2,
        "Discussion": 3,
        "Conclusion": 4,
        "References": 5,
    }
    seen = set()
    normalized_sections: List[OutlineSection] = []
    for s in sections:
        canonical_title = _canonicalize_outline_title(s.title)
        key = _normalize_heading(canonical_title)
        if key in seen:
            continue
        seen.add(key)
        s.title = canonical_title
        normalized_sections.append(s)
    return sorted(normalized_sections, key=lambda s: order.get(s.title, 99))


def _normalize_outline_payload(sections: List[OutlineSection], paper_ids: List[str]) -> List[OutlineSection]:
    normalized_sections: List[OutlineSection] = []
    for index, section in enumerate(_order_outline_sections(sections), start=1):
        normalized_sections.append(
            OutlineSection(
                id=section.id or f"section-{index}-{uuid.uuid4().hex[:8]}",
                title=section.title,
                description=section.description.strip(),
                status=section.status or "pending",
                relevant_paper_ids=section.relevant_paper_ids or list(paper_ids),
                recommended_asset_types=section.recommended_asset_types or [],
            )
        )
    return normalized_sections


class ResearchQuestionRequest(BaseModel):
    """Request for research question answering"""
    question: str
    project_id: Optional[str] = None
    max_papers: int = 5
    use_existing_papers: bool = False  # Use papers already in project library
    selected_paper_ids: List[str] = []


class ResearchAnswerResponse(BaseModel):
    """Structured research answer"""
    summary: str
    key_points: List[str]
    recommended_actions: List[str]
    explanation_steps: List[str]
    confidence: str
    notes: Optional[str] = None
    papers: List[Dict]
    query_analysis: Dict


@router.post("/answer", response_model=ResearchAnswerResponse)
async def answer_research_question(
    request: ResearchQuestionRequest,
    db: Session = Depends(get_db)
):
    """
    Complete research workflow: Search papers, analyze, and generate structured answer
    
    Flow:
    1. Analyze query (expand and optimize)
    2. Search papers from arXiv + Semantic Scholar
    3. Rank papers by quality
    4. Extract context (abstracts or PDF chunks if available)
    5. Generate structured answer with citations
    """
    
    try:
        # Step 1: Query Analysis
        logger.info(f"Analyzing query: {request.question}")
        analysis = await query_analyzer.analyze_query(request.question)
        optimized_query = analysis.get("search_query", request.question)
        
        # Step 2: Search Papers
        logger.info(f"Searching for: {optimized_query}")
        papers = search_all_sources(optimized_query, max_results_per_source=request.max_papers)
        
        if not papers:
            # Try expanded queries if primary fails
            if analysis.get("expanded_queries"):
                for exp_query in analysis["expanded_queries"][:2]:
                    papers = search_all_sources(exp_query, max_results_per_source=3)
                    if papers:
                        break
        
        if not papers:
            raise HTTPException(status_code=404, detail="No papers found for this query")
        
        # Step 3: Rank Papers (simple scoring for now)
        ranked_papers = _rank_papers(papers, request.question)
        
        # Step 4: Extract Context
        # Use abstracts as context (full PDF processing is optional)
        context_chunks = []
        paper_metadata = []
        
        for paper in ranked_papers[:5]:  # Top 5 papers
            context_chunks.append(paper.get('summary', ''))
            paper_metadata.append({
                'title': paper.get('title'),
                'authors': paper.get('authors', [])[:3] if isinstance(paper.get('authors'), list) else [],
                'year': paper.get('year'),
                'source': paper.get('source')
            })
        
        # Step 5: Generate Structured Answer
        logger.info("Generating structured answer")
        answer = await answer_generator.generate_answer(
            question=request.question,
            context_chunks=context_chunks,
            paper_metadata=paper_metadata
        )
        
        # Return response
        return ResearchAnswerResponse(
            summary=answer.get('summary', ''),
            key_points=answer.get('key_points', []),
            recommended_actions=answer.get('recommended_actions', []),
            explanation_steps=answer.get('explanation_steps', []),
            confidence=answer.get('confidence', 'medium'),
            notes=answer.get('notes'),
            papers=ranked_papers[:5],
            query_analysis=analysis
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in research workflow: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _rank_papers(papers: List[Dict], query: str) -> List[Dict]:
    """
    Rank papers by relevance and quality
    
    Scoring factors:
    - Source reputation (arXiv, conferences, journals)
    - Recency
    - Has PDF available
    - Citation count (if available)
    """
    
    for paper in papers:
        score = 0.0
        
        # Recency (max 3.0 points)
        year = paper.get('year')
        if year:
            age = 2026 - int(year)
            recency_score = max(0, 3.0 - (age * 0.2))
            score += recency_score
        
        # Has PDF (2.0 points)
        if paper.get('pdf_url'):
            score += 2.0
        
        # Reputable source (3.0 points)
        venue = paper.get('venue', '').lower()
        source = paper.get('source', '').lower()
        
        reputable_keywords = [
            'ieee', 'acm', 'springer', 'nature', 'science',
            'neurips', 'icml', 'cvpr', 'acl', 'emnlp', 'aaai',
            'iclr', 'kdd', 'www', 'sigir'
        ]
        
        is_reputable = any(keyword in venue for keyword in reputable_keywords)
        if is_reputable or source == 'arxiv':
            score += 3.0
        
        # Citation count (max 2.0 points)
        if paper.get('citation_count'):
            # Log scale for citations
            import math
            citation_score = min(2.0, math.log10(paper['citation_count'] + 1) / 2)
            score += citation_score
        
        paper['score'] = round(score, 2)
        paper['is_reputable'] = is_reputable
    
    # Sort by score descending
    papers.sort(key=lambda p: p.get('score', 0), reverse=True)
    return papers


@router.post("/stream-search")
async def stream_research_search(request: ResearchQuestionRequest):
    """
    Stream research workflow with real-time updates (SSE)
    
    Sends events:
    - analyzing: Query analysis results
    - searching: Search progress
    - ranking: Paper ranking
    - generating: Answer generation
    - complete: Final answer
    """
    
    async def event_generator():
        try:
            # Step 1: Analyze
            yield f"data: {json.dumps({'type': 'analyzing', 'message': 'Analyzing your question...'})}\n\n"
            
            analysis = await query_analyzer.analyze_query(request.question)
            
            # Stream the Chain of Thought
            if "thought" in analysis:
                 yield f"data: {json.dumps({'type': 'log', 'data': {'source': 'Thought', 'message': analysis['thought']}})}\n\n"
            
            yield f"data: {json.dumps({'type': 'analyzed', 'data': analysis})}\n\n"
            
            await asyncio.sleep(0.1)
            
            # Step 2: Search
            yield f"data: {json.dumps({'type': 'searching', 'message': f'Searching for papers...'})}\n\n"
            
            optimized_query = analysis.get('search_query', request.question)
            papers = search_all_sources(optimized_query, max_results_per_source=request.max_papers)
            
            yield f"data: {json.dumps({'type': 'found', 'count': len(papers)})}\n\n"
            
            await asyncio.sleep(0.1)
            
            # Step 3: Rank
            yield f"data: {json.dumps({'type': 'ranking', 'message': 'Ranking papers by quality...'})}\n\n"
            
            ranked_papers = _rank_papers(papers, request.question)
            
            yield f"data: {json.dumps({'type': 'ranked', 'data': ranked_papers[:5]})}\n\n"
            
            await asyncio.sleep(0.1)
            
            # Step 4: Generate Answer
            yield f"data: {json.dumps({'type': 'generating', 'message': 'Generating answer...'})}\n\n"
            
            # Extract context
            context_chunks = [p.get('summary', '') for p in ranked_papers[:5]]
            
            paper_metadata = []
            for p in ranked_papers[:5]:
                paper_metadata.append({
                    'title': p.get('title'),
                    'authors': p.get('authors', []),
                    'year': p.get('year'),
                    'source': p.get('source', 'Unknown')
                })
            
            # Generate Answer (Real or Mock via AnswerGenerator config)
            answer = await answer_generator.generate_answer(
                question=request.question,
                context_chunks=context_chunks,
                paper_metadata=paper_metadata
            )
            
            # Step 5: Complete
            yield f"data: {json.dumps({'type': 'complete', 'answer': answer, 'papers': ranked_papers[:5]})}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/outline", response_model=OutlineResponse)
async def generate_outline(
    request: OutlineRequest,
    db: Session = Depends(get_db)
):
    """
    Generate outline/plan for existing project based on selected papers
    """
    try:
        # Verify project exists
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Fetch selected papers (optional)
        papers = []
        if request.paper_ids:
            papers = db.query(LibraryItem).filter(
                LibraryItem.id.in_(request.paper_ids),
                LibraryItem.project_id == request.project_id
            ).all()
        
        if not papers:
            logger.warning(f"No papers found for outline generation in project {request.project_id}. Generating generic outline.")
        
        # Build context for planner
        paper_context = "\n".join([f"- {p.title}: {p.abstract[:200]}..." for p in papers]) if papers else "No papers selected."
        
        # Run planner agent
        from app.agents.graph import planner_node
        
        mock_state = {
            "query": f"Generate a comprehensive research outline for these papers:\n{paper_context}",
            "selected_paper_ids": request.paper_ids,
            "lab_asset_ids": request.asset_ids
        }
        
        result = await planner_node(mock_state)
        current_draft = result.get("current_draft", {})
        outline_text = current_draft.get("outline", "# Research Plan")
        sections_plan = current_draft.get("sections_plan", [])
        
        # Update project with generated outline
        project.findings = outline_text
        db.commit()
        
        # Parse outline into sections (simple parsing)
        sections: List[OutlineSection] = []
        if sections_plan:
            for raw_section in sections_plan:
                sections.append(
                    OutlineSection(
                        id=raw_section.get("id"),
                        title=raw_section.get("title", "Section"),
                        description=raw_section.get("description", "").strip(),
                        status=raw_section.get("status", "pending"),
                        relevant_paper_ids=raw_section.get("relevant_paper_ids", request.paper_ids),
                        recommended_asset_types=raw_section.get("recommended_asset_types", []),
                    )
                )
        else:
            lines = outline_text.split('\n')
            current_section = None
            
            for line in lines:
                if line.startswith('## '):
                    if current_section:
                        sections.append(current_section)
                    current_section = OutlineSection(
                        id=f"section-{len(sections) + 1}-{uuid.uuid4().hex[:8]}",
                        title=line.replace('## ', '').strip(),
                        description="",
                        status="pending",
                        relevant_paper_ids=request.paper_ids,
                        recommended_asset_types=[]
                    )
                elif current_section and line.strip():
                    if line.lower().startswith("description:"):
                        current_section.description += line.replace("Description:", "", 1).strip() + "\n"
                    else:
                        current_section.description += line + "\n"
            
            if current_section:
                sections.append(current_section)

        # Fallback: if parsing failed, create a default outline
        if not sections:
            default_titles = ["Introduction", "Methodology", "Results", "Discussion", "Conclusion", "References"]
            sections = [
                OutlineSection(
                    id=f"section-{index + 1}-{uuid.uuid4().hex[:8]}",
                    title=title,
                    description="",
                    status="pending",
                    relevant_paper_ids=request.paper_ids,
                    recommended_asset_types=[]
                )
                for index, title in enumerate(default_titles)
            ]

        sections = _normalize_outline_payload(sections, request.paper_ids)

        draft = db.query(Draft).filter(Draft.project_id == request.project_id).first()
        if not draft:
            draft = Draft(project_id=request.project_id)
            db.add(draft)
        draft.outline = [section.model_dump() for section in sections]
        db.commit()

        logger.info(f"Generated outline with {len(sections)} sections for project {request.project_id}")
        
        return OutlineResponse(sections=sections)
        
    except Exception as e:
        logger.error(f"Error generating outline: {e}", exc_info=True)
        # Return empty outline on error
        return OutlineResponse(sections=[])

# ===== DRAFT PERSISTENCE =====

@router.post("/draft/save")
async def save_draft(
    request: SaveDraftRequest,
    db: Session = Depends(get_db)
):
    """Save draft outline and content for a project"""
    try:
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get or create draft for this project
        draft = db.query(Draft).filter(Draft.project_id == request.project_id).first()
        
        if not draft:
            draft = Draft(project_id=request.project_id)
            db.add(draft)
        
        # Update outline if provided
        if request.outline is not None:
            draft.outline = request.outline
        
        # Update content if provided
        if request.content is not None:
            draft.full_content = request.content
            # Update word count
            draft.word_count = len(request.content.split())
        
        db.commit()
        db.refresh(draft)
        
        logger.info(f"Saved draft for project {request.project_id}")
        
        return {
            "id": draft.id,
            "project_id": draft.project_id,
            "outline": draft.outline,
            "full_content": draft.full_content,
            "word_count": draft.word_count,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving draft: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/draft/load/{project_id}")
async def load_draft(
    project_id: str,
    db: Session = Depends(get_db)
):
    """Load saved draft outline and content for a project"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get draft if exists
        draft = db.query(Draft).filter(Draft.project_id == project_id).first()
        
        if not draft:
            # Return empty draft if none exists
            return {
                "id": None,
                "project_id": project_id,
                "outline": None,
                "full_content": None,
                "word_count": 0,
                "created_at": None,
                "updated_at": None
            }
        
        logger.info(f"Loaded draft for project {project_id}")
        
        return {
            "id": draft.id,
            "project_id": draft.project_id,
            "outline": draft.outline,
            "full_content": draft.full_content,
            "word_count": draft.word_count,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading draft: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/assets/upload", response_model=ResearchAssetResponse)
async def upload_research_asset(
    project_id: str,
    file: UploadFile = File(...),
    name: str = Form(...),
    asset_type: ResearchAssetType = Form(...),
    description: Optional[str] = Form(None),
    methodology_note: Optional[str] = Form(None),
    section_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Upload a student-owned research artifact used in original paper drafting."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    asset = await research_asset_service.ingest_research_asset(
        project_id=project_id,
        file=file,
        asset_type=asset_type.value,
        name=name,
        description=description,
        methodology_note=methodology_note,
        section_hint=section_hint,
        db=db,
    )
    return asset


@router.get("/projects/{project_id}/assets", response_model=List[ResearchAssetResponse])
async def list_research_assets(
    project_id: str,
    db: Session = Depends(get_db),
):
    """List student-owned research artifacts for a project."""
    assets = db.query(ResearchAsset).filter(
        ResearchAsset.project_id == project_id
    ).order_by(ResearchAsset.updated_at.desc()).all()
    return assets
