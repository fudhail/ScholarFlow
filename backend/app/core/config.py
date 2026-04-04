"""Application configuration using Pydantic Settings"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Google Gemini API (REQUIRED - must be set in .env file)
    google_api_key: str
    
    # Anam.ai API Key (Optional)
    anam_api_key: str | None = None
    
    # Database
    database_url: str = "sqlite:///./data/scholarflow.db"

    # Feature Flags - Set to False for production
    mock_ai_responses: bool = False

    # AI / LLM Configuration
    llm_provider: str = "hybrid"  # "gemini", "ollama", "hybrid"
    
    # Gemini Config (Fallback & Vision)
    text_model_name: str = "scholarmate"
    fast_model_name: str = "scholarmate"
    vision_model_name: str = "gemini-1.5-flash"
    
    # Ollama Config (Primary for hybrid mode)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_fast: str = "llama3.2:1b"  # Fast 1B model for quick tasks (routing, intent)
    ollama_model_smart: str = "scholarmate"  # Smart 3B model for quality tasks (writing, synthesis)
    ollama_model_search: str = "scholarflow-search"  # 1B model optimized for paper relevance scoring (research mode)
    ollama_model_studio: str = "scholarflow-studio"  # 3B model optimized for original academic writing (studio mode)
    
    # Hybrid Mode Settings
    use_ollama_for_chat: bool = True     # Chat -> Ollama
    use_ollama_for_writing: bool = True  # Writing -> Ollama
    use_ollama_for_ranking: bool = True  # Ranking -> Ollama (was False)
    use_gemini_for_vision: bool = True   # Vision -> Gemini (Keep True)
    
    # Chain-of-Thought Settings
    enable_cot_reasoning: bool = False   # Enable explicit Chain-of-Thought prompting
    show_thinking_to_user: bool = False  # Stream thinking process to UI (if CoT enabled)

    # Research-grounding policy
    research_focused_mode: bool = True  # Factual answers should be grounded in retrieved papers
    enforce_paper_citations: bool = True  # Reject grounded answers that contain no paper citations
    auto_research_on_factual_queries: bool = True  # Auto-route factual chat to paper search when context is missing
    
    # Application
    app_env: str = "development"
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Paths
    faiss_index_path: Path = BACKEND_ROOT / "data" / "indexes"
    upload_path: Path = BACKEND_ROOT / "data" / "uploads"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # LangGraph Configuration
    max_search_iterations: int = 3  # Discovery Loop limit
    max_revision_iterations: int = 2  # Review Loop limit
    relevance_threshold: float = 0.6  # Paper ranking threshold
    
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        """Accept common environment variants like DEBUG=release."""
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"release", "prod", "production", "false", "0", "off", "no"}:
                return False
            if lowered in {"debug", "dev", "development", "true", "1", "on", "yes"}:
                return True
        return value
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.faiss_index_path.mkdir(parents=True, exist_ok=True)
        self.upload_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
