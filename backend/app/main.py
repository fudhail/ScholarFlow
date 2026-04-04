"""FastAPI application entry point"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager

class LimitUploadSize(BaseHTTPMiddleware):
    def __init__(self, app, max_upload_size: int) -> None:
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next):
        if request.method == 'POST':
            if 'content-length' in request.headers:
                content_length = int(request.headers['content-length'])
                if content_length > self.max_upload_size:
                    return JSONResponse(status_code=413, content={"detail": "File too large"})
        return await call_next(request)

from app.core.config import settings
from app.models.database import init_db
from app.api import chat, projects, lab, papers, research, voice, agents
from app.core.logging import setup_logging
import logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    # Startup
    logger.info("[STARTUP] Initializing ScholarFlow Backend...")
    init_db()
    
    # Ensure uploads directory exists
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    
    # Verify Discovery Project
    # in a real app, this logic might be in init_db, but safe to double check or rely on reset_db
    logger.info("[OK] Database initialized")
    
    yield
    
    # Shutdown
    logger.info("[SHUTDOWN] Shutting down...")


# Create FastAPI application
app = FastAPI(
    title="ScholarFlow API",
    description="Research Assistant Agent Backend",
    version="0.1.0",
    lifespan=lifespan
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(LimitUploadSize, max_upload_size=50 * 1024 * 1024) # 50MB limit


# Include API Routers
app.include_router(chat.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(lab.router, prefix="/api/v1")
app.include_router(papers.router, prefix="/api/v1")
app.include_router(research.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")  # Specialized agents
app.include_router(voice.router)  # Voice endpoints for avatar

from app.api import avatar, export
app.include_router(avatar.router, prefix="/api/v1")  # Anam.ai Avatar
app.include_router(export.router, prefix="/api/v1")  # LaTeX/PDF Export pipeline

# Mount Uploads for Static Access (PDF Viewer)
from fastapi.staticfiles import StaticFiles
import os

settings.upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_path)), name="uploads")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ScholarFlow Backend",
        "version": "0.1.0"
    }


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "ScholarFlow Backend API",
        "docs": "/docs",
        "health": "/health",
        "features": {
            "multi_agent_workflows": "LangGraph with cyclic graphs",
            "discovery_loop": "Iterative paper search refinement",
            "review_loop": "Draft revision with AI reviewer",
            "multimodal_analysis": "Gemini Vision for lab assets",
            "vector_store": "FAISS-based RAG",
            "streaming": "Server-Sent Events for real-time updates"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
