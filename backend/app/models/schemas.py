"""Pydantic schemas for API request/response validation"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ===== ENUMS =====

class ProjectMode(str, Enum):
    """Project mode types"""
    RESEARCH = "RESEARCH"
    MANUSCRIPT = "MANUSCRIPT"


class ProjectKind(str, Enum):
    """What kind of work the user is trying to create."""
    LIT_REVIEW = "LIT_REVIEW"
    EXPERIMENTAL = "EXPERIMENTAL"
    MANUSCRIPT = "MANUSCRIPT"


class AssetType(str, Enum):
    """Lab asset types"""
    IMAGE = "image"
    DATA = "data"
    CODE = "code"


class ResearchAssetType(str, Enum):
    """Student research asset types"""
    EXPERIMENT_DATA = "experiment_data"
    MY_FIGURE = "my_figure"
    MY_CODE = "my_code"
    MY_TABLE = "my_table"
    METHODOLOGY = "methodology"


class AgentIntent(str, Enum):
    """User intent classification"""
    SEARCH = "SEARCH"
    CHAT = "CHAT"
    DRAFT = "DRAFT"
    ANALYZE = "ANALYZE"


# ===== PROJECT SCHEMAS =====

class ProjectCreate(BaseModel):
    """Request schema for creating a project"""
    title: str = Field(..., min_length=1, max_length=255)
    description: str
    mode: ProjectMode
    project_kind: Optional[ProjectKind] = None
    methodology: Optional[str] = None
    findings: Optional[str] = None


class ProjectResponse(BaseModel):
    """Response schema for project data"""
    id: str
    title: str
    description: str
    mode: str
    project_kind: Optional[str] = None
    current_phase: Optional[str] = None
    methodology: Optional[str]
    findings: Optional[str]
    created_at: datetime
    updated_at: datetime
    library_items: List["LibraryItemResponse"] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


# ===== LIBRARY SCHEMAS =====

class LibraryItemCreate(BaseModel):
    """Request schema for adding a library item"""
    title: str
    authors: List[str]
    year: Optional[int] = None
    abstract: str
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None


class LibraryItemResponse(BaseModel):
    """Response schema for library item"""
    id: str
    project_id: str
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    url: Optional[str]
    pdf_path: Optional[str]
    chunk_count: int
    is_selected_for_context: bool
    relevance_score: Optional[float]
    created_at: datetime
    
    
    @validator("authors", pre=True)
    def validate_authors(cls, v):
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except:
                return [v] # Fallback
        return v

    class Config:
        from_attributes = True


class LibraryPageResponse(BaseModel):
    """Paginated library response"""
    items: List[LibraryItemResponse]
    total: int
    page: int
    limit: int
    pages: int


# ===== LAB ASSET SCHEMAS =====

class LabAssetCreate(BaseModel):
    """Request schema for uploading lab asset"""
    name: str
    asset_type: AssetType


class LabAssetResponse(BaseModel):
    """Response schema for lab asset"""
    id: str
    project_id: str
    name: str
    asset_type: str
    file_path: str
    ai_description: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ===== RESEARCH ASSET SCHEMAS (NEW) =====

class ResearchAssetCreate(BaseModel):
    """Request schema for uploading student research asset"""
    name: str
    asset_type: ResearchAssetType
    description: Optional[str] = None
    methodology_note: Optional[str] = None
    section_hint: Optional[str] = None  # "methods" | "results" | "discussion"


class ResearchAssetResponse(BaseModel):
    """Response schema for research asset"""
    id: str
    project_id: str
    name: str
    asset_type: str
    description: Optional[str]
    file_path: str
    methodology_note: Optional[str]
    section_hint: Optional[str]
    is_included_in_draft: bool
    ai_analysis: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ===== CHAT/WORKFLOW SCHEMAS =====

class ChatMessage(BaseModel):
    """Single chat message"""
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatRequest(BaseModel):
    """Request schema for chat/workflow stream"""
    project_id: str
    session_id: Optional[str] = None  # NEW: Target specific chat session
    message: str
    selected_paper_ids: List[str] = Field(default_factory=list)
    lab_asset_ids: List[str] = Field(default_factory=list)
    research_asset_ids: List[str] = Field(default_factory=list)  # NEW: Student's research data
    current_section: Optional[str] = None  # NEW: Which section is being drafted


class WorkflowStepLog(BaseModel):
    """Log entry for workflow step"""
    step: str  # "router" | "search" | "rank" | "writer" | "reviewer"
    source: str  # Agent name
    message: str
    status: str = "processing"  # "processing" | "completed" | "error"
    metadata: Optional[Dict[str, Any]] = None


# ===== DRAFT SCHEMAS =====

class SectionDraftRequest(BaseModel):
    """Request schema for drafting a section"""
    project_id: str
    section_title: str
    section_description: str
    relevant_paper_ids: List[str]
    lab_asset_ids: List[str] = []
    style: str = "IEEE"


class OutlineSection(BaseModel):
    """Manuscript outline section"""
    id: Optional[str] = None
    title: str
    description: str
    status: str = "pending"
    relevant_paper_ids: List[str] = Field(default_factory=list)
    recommended_asset_types: List[str] = Field(default_factory=list)


class OutlineRequest(BaseModel):
    """Request schema for generating outline"""
    project_id: str
    paper_ids: List[str]
    asset_ids: List[str] = []
    style: str = "IEEE"


class OutlineResponse(BaseModel):
    """Response schema for outline"""
    sections: List[OutlineSection]


class SaveDraftRequest(BaseModel):
    """Request schema for saving draft outline and content"""
    project_id: str
    outline: Optional[List[Dict[str, Any]]] = None  # List of outline sections
    content: Optional[str] = None  # Full paper content


class DraftResponse(BaseModel):
    """Response schema for draft"""
    id: str
    project_id: str
    outline: Optional[List[Dict[str, Any]]]
    full_content: Optional[str]
    word_count: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ===== SEARCH SCHEMAS =====

class PaperSearchRequest(BaseModel):
    """Request schema for paper search"""
    query: str
    max_results: int = 10
    source: str = "arxiv"  # "arxiv" | "semantic_scholar"


class PaperSearchResult(BaseModel):
    """Single paper search result"""
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    url: Optional[str]
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    relevance_score: Optional[float] = None


class PaperSearchResponse(BaseModel):
    """Response schema for paper search"""
    results: List[PaperSearchResult]
    total_count: int
    source: str


# ===== CITATION SCHEMAS =====

class Citation(BaseModel):
    """BibTeX citation entry"""
    key: str
    bibtex: str
    paper_id: str


class CitationResponse(BaseModel):
    """Response schema for citations"""
    citations: List[Citation]
    bibtex_file: str  # Full .bib file content
