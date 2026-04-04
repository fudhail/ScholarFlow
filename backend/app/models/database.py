"""SQLAlchemy database models for persistence"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Boolean, ForeignKey, Float, JSON, Enum, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from typing import Optional
import uuid
import enum

from app.core.config import settings


class ProjectPhase(enum.Enum):
    """Project lifecycle phases"""
    DISCOVERY = "discovery"      # Finding and reading papers
    READING = "reading"           # Annotating literature
    ANALYSIS = "analysis"         # Student conducting research
    DRAFTING = "drafting"         # Writing manuscript
    REVISION = "revision"         # Editing and polishing


# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Project(Base):
    """Research project (isolation context for RAG and chat history)"""
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    mode = Column(String(50), nullable=False)  # RESEARCH | MANUSCRIPT
    project_kind = Column(String(50), nullable=False, default="MANUSCRIPT")  # LIT_REVIEW | EXPERIMENTAL | MANUSCRIPT
    
    # NEW: Project phase tracking
    current_phase = Column(Enum(ProjectPhase), default=ProjectPhase.DISCOVERY)
    phase_history = Column(JSON, default=list)  # Track phase transitions
    
    # Optional context fields
    methodology = Column(Text, nullable=True)
    findings = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    library_items = relationship("LibraryItem", back_populates="project", cascade="all, delete-orphan")
    lab_assets = relationship("LabAsset", back_populates="project", cascade="all, delete-orphan")
    research_assets = relationship("ResearchAsset", back_populates="project", cascade="all, delete-orphan")  # NEW
    drafts = relationship("Draft", back_populates="project", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="project", cascade="all, delete-orphan")


class LibraryItem(Base):
    """PDF documents in project library (vector-indexed)"""
    __tablename__ = "library_items"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Paper metadata
    title = Column(String(500), nullable=False)
    authors = Column(JSON)  # List of author names
    year = Column(Integer, nullable=True)
    abstract = Column(Text)
    
    # File and vector storage
    pdf_path = Column(String(500), nullable=True)
    vector_id = Column(String(100), nullable=True)  # Reference to FAISS index
    chunk_count = Column(Integer, default=0)
    
    # RAG context control
    is_selected_for_context = Column(Boolean, default=True)
    relevance_score = Column(Float, nullable=True)  # From ranking agent
    
    # External IDs
    arxiv_id = Column(String(100), nullable=True)
    doi = Column(String(200), nullable=True)
    url = Column(String(500), nullable=True)  # External URL fallback
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="library_items")


class LabAsset(Base):
    """Multimodal assets (images, CSV) with AI-generated descriptions"""
    __tablename__ = "lab_assets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False)  # image | data | code
    file_path = Column(String(500), nullable=False)
    
    # AI-generated description (from Gemini Vision for images)
    ai_description = Column(Text, nullable=True)
    
    # Metadata
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="lab_assets")


class ResearchAsset(Base):
    """Student's OWN research artifacts (experimental data, figures, protocols)"""
    __tablename__ = "research_assets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    name = Column(String(255), nullable=False)
    asset_type = Column(String(50), nullable=False)  # experiment_data | my_figure | my_code | my_table | methodology
    description = Column(Text)  # Student's description
    file_path = Column(String(500), nullable=False)
    
    # Research context
    methodology_note = Column(Text, nullable=True)  # How this was generated
    section_hint = Column(String(50), nullable=True)  # methods | results | discussion
    is_included_in_draft = Column(Boolean, default=True)
    
    # AI analysis (optional)
    ai_analysis = Column(Text, nullable=True)  # AI interpretation of the data/figure
    
    # Metadata
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="research_assets")



class Draft(Base):
    """Manuscript drafts with structured content blocks"""
    __tablename__ = "drafts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Content stored as JSON blocks
    content_blocks = Column(JSON)  # [{section: "Intro", text: "...", status: "completed"}]
    
    # NEW: Full paper content (plain text or markdown)
    full_content = Column(Text, nullable=True)
    
    # NEW: Outline/plan for the paper
    outline = Column(JSON, nullable=True)  # [{id, title, description, status, relevantPaperIds}]
    
    # Bibliography tracking
    bibliography = Column(JSON)  # [{key: "smith2020", bibtex: "..."}]
    
    # Draft metadata
    word_count = Column(Integer, default=0)
    revision_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="drafts")


class ChatSession(Base):
    """Chat history for a project"""
    __tablename__ = "chat_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    # Session metadata
    title = Column(String(255), default="New Chat")  # NEW: Named sessions
    
    # Messages stored as JSON
    messages = Column(JSON)  # [{role: "user", content: "..."}, {role: "assistant", content: "..."}]
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="chat_sessions")


# Create all tables
def _ensure_column(table_name: str, column_name: str, ddl: str) -> None:
    """Add a missing column for SQLite workspaces that were created before newer models."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return

    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def init_db():
    """Initialize database tables and backfill a few drifted columns for SQLite dev DBs."""
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name == "sqlite":
        _ensure_column("projects", "project_kind", "project_kind VARCHAR(50) NOT NULL DEFAULT 'MANUSCRIPT'")
        _ensure_column("library_items", "url", "url VARCHAR(500)")
        _ensure_column("chat_sessions", "title", "title VARCHAR(255) DEFAULT 'New Chat'")
        _ensure_column("drafts", "full_content", "full_content TEXT")
        _ensure_column("drafts", "outline", "outline JSON")


if __name__ == "__main__":
    init_db()
    print("✅ Database initialized successfully")
