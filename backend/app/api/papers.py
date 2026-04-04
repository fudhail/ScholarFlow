"""Paper management and upload API"""
import os
import shutil
import fitz  # PyMuPDF
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
import os
import math
import io

from app.models.database import get_db, LibraryItem, Project
from app.models.schemas import LibraryItemResponse, LibraryPageResponse, PaperSearchResponse, PaperSearchResult
from app.services.vector_store import vector_store
from app.services.paper_search import search_all_sources
from app.core.config import settings
import logging

router = APIRouter(prefix="/papers", tags=["papers"])
logger = logging.getLogger(__name__)

# Ensure upload directory exists
UPLOAD_DIR = settings.upload_path
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
logger.info(f"Upload directory checked: {UPLOAD_DIR}")


@router.post("/add-to-library", response_model=LibraryItemResponse)
async def add_paper_to_library(
    project_id: str,
    paper_data: dict,
    db: Session = Depends(get_db)
):
    """
    Add a discovered paper to project library
    
    Args:
        project_id: Project ID to add paper to
        paper_data: Paper data from discovery (id, title, authors, year, summary, pdfUrl, source)
    """
    try:
        # Check if paper already exists in this project
        existing = db.query(LibraryItem).filter(
            LibraryItem.project_id == project_id,
            LibraryItem.id == paper_data.get('id')
        ).first()
        
        if existing:
            logger.info(f"Paper {paper_data.get('id')} already in library")
            return existing
        
        # Create new library item
        new_paper = LibraryItem(
            id=paper_data.get('id'),
            project_id=project_id,
            title=paper_data.get('title', 'Untitled'),
            authors=paper_data.get('authors', []),
            year=paper_data.get('year'),
            abstract=paper_data.get('summary', ''),
            arxiv_id=paper_data.get('arxiv_id'),
            doi=paper_data.get('doi'),
            url=paper_data.get('pdfUrl'),
            is_selected_for_context=False,  # Not selected by default
            chunk_count=0
        )
        
        db.add(new_paper)
        db.commit()
        db.refresh(new_paper)
        
        logger.info(f"Added paper {new_paper.id} to library for project {project_id}")
        return new_paper
        
    except Exception as e:
        logger.error(f"Error adding paper to library: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/library", response_model=LibraryPageResponse)
async def list_library_items(
    project_id: str,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """List library items for a project with pagination"""
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")

    query = db.query(LibraryItem).filter(LibraryItem.project_id == project_id)
    total = query.count()
    pages = max(1, math.ceil(total / limit))
    offset = (page - 1) * limit

    items = query.order_by(LibraryItem.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }


@router.get("/search", response_model=PaperSearchResponse)
async def search_papers(
    query: str,
    max_results: int = 10
):
    """
    Search for papers from ArXiv and Semantic Scholar
    
    Args:
        query: Search query
        max_results: Maximum number of results to return (default: 10)
    
    Returns:
        PaperSearchResponse with list of papers and metadata
    """
    try:
        # Search using the multi-source search service
        papers = search_all_sources(query, max_results_per_source=max_results // 2)
        
        # Transform to PaperSearchResult schema
        results = []
        for paper in papers:
            results.append(PaperSearchResult(
                title=paper.get('title', ''),
                authors=paper.get('authors', []),
                year=paper.get('year'),
                abstract=paper.get('abstract') or paper.get('summary', ''),
                url=paper.get('url') or paper.get('pdf_url'),
                arxiv_id=paper.get('arxiv_id'),
                doi=paper.get('doi'),
                relevance_score=paper.get('citation_count', 0) / 1000.0 if paper.get('citation_count') else None
            ))
        
        return PaperSearchResponse(
            results=results,
            total_count=len(results),
            source="arxiv+semantic_scholar"
        )
        
    except Exception as e:
        logger.error(f"Error in paper search: {e}", exc_info=True)
        # Return empty results instead of failing
        return PaperSearchResponse(
            results=[],
            total_count=0,
            source="error"
        )


@router.get("/{paper_id}", response_model=LibraryItemResponse)
async def get_paper(
    paper_id: str,
    db: Session = Depends(get_db)
):
    """Get paper details by ID"""
    paper = db.query(LibraryItem).filter(LibraryItem.id == paper_id).first()
    if not paper:
        # Check if it's a mock ID, if so, handled by frontend, but 404 here
        raise HTTPException(status_code=404, detail="Paper not found")
        
    # Return path relative to mount for frontend usage if needed, 
    # but LibraryItemResponse has pdf_path. 
    # We might want to normalize it for the frontend.
    # The frontend will construction /uploads/{filename} based on pdf_path.
    return paper

def process_pdf_background(
    file_path: Path,
    paper_id: str,
    project_id: str,
    db_session_factory
):
    """
    Refined PDF processing in background.
    
    Uses page-tracked chunking for PDF-to-page linking in citations.
    """
    from app.services.pdf_processor import chunk_pdf_with_pages
    
    db = db_session_factory()
    try:
        # 1. Extract Text with PAGE TRACKING
        chunks_with_pages = chunk_pdf_with_pages(file_path)
        
        if not chunks_with_pages:
            # Fallback to PyMuPDF if pdfplumber fails
            import fitz
            doc = fitz.open(file_path)
            chunks_with_pages = []
            
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                if text.strip():
                    # Create chunks with page tracking
                    page_chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
                    for chunk in page_chunks:
                        chunks_with_pages.append({
                            "text": chunk,
                            "page_number": page_num,
                            "source_file": file_path.name
                        })
            doc.close()
            
        # 2. Update Database Record
        paper = db.query(LibraryItem).filter(LibraryItem.id == paper_id).first()
        if paper:
            paper.chunk_count = len(chunks_with_pages)
            db.commit()
            
        # 3. Vector Indexing WITH PAGE NUMBERS
        if chunks_with_pages:
            vector_store.add_document_chunks_with_pages(
                project_id=project_id,
                paper_id=paper_id,
                chunks_with_pages=chunks_with_pages
            )
            logger.info(f"Indexed {len(chunks_with_pages)} page-tracked chunks for {paper_id}")
            
    except Exception as e:
        logger.error(f"Error processing PDF {paper_id}: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/upload", response_model=LibraryItemResponse)
async def upload_paper(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Upload PDF, parse text, and index for RAG"""
    
    # Validation
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save File
    file_id = f"{project_id}_{int(datetime.now().timestamp())}"
    safe_filename = file.filename.replace(" ", "_").replace("/", "_")
    file_path = UPLOAD_DIR / f"{file_id}_{safe_filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Create DB Entry
    new_paper = LibraryItem(
        project_id=project_id,
        title=file.filename.replace('.pdf', '').replace('_', ' ').title(),
        authors=["Unknown"], # Placeholder until we parse metadata
        year=datetime.now().year,
        abstract="Processing...",
        pdf_path=str(file_path),
        chunk_count=0,
        is_selected_for_context=True
    )
    
    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)
    
    # Trigger Background Processing (avoid blocking response)
    # Pass session factory, not session, to background task
    from app.models.database import SessionLocal
    background_tasks.add_task(
        process_pdf_background, 
        file_path, 
        new_paper.id, 
        project_id, 
        SessionLocal
    )

    return new_paper


@router.get("/pdf/proxy/{arxiv_id}")
async def proxy_arxiv_pdf(arxiv_id: str):
    """
    Proxy ArXiv PDF downloads to bypass CORS issues.
    The backend fetches the PDF and streams it to the client.

    Args:
        arxiv_id: ArXiv paper ID (e.g., "1706.03762" or "1706.03762v2")

    Returns:
        StreamingResponse with PDF bytes
    """
    try:
        import httpx

        # Clean arxiv_id (remove version suffix if present)
        clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id

        # Download PDF from ArXiv
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                pdf_url,
                timeout=30,
                follow_redirects=True,
                headers={'User-Agent': 'ScholarFlow/1.0'}
            )
            response.raise_for_status()
            pdf_bytes = response.content

        if not pdf_bytes:
            raise HTTPException(status_code=404, detail=f"PDF not found for ArXiv ID: {arxiv_id}")

        # Stream PDF to client with proper headers
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=arxiv_{clean_id}.pdf"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to proxy ArXiv PDF {arxiv_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch PDF: {str(e)}")
