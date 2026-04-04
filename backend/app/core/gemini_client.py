"""Google Gemini AI client singleton using LangChain integration"""

from typing import AsyncIterator, Optional
from pathlib import Path
import base64
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from .config import settings


class GeminiClient:
    """Singleton client for Google Gemini API via LangChain"""
    
    _instance: Optional['GeminiClient'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize LangChain Gemini models"""
        
        # Common configuration
        # Note: safety_settings can be passed here if needed, but defaults are usually fine for standard use.
        # If strict safety settings are required, they can be added to the constructor.
        
        self.text_model = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=settings.google_api_key,
            temperature=0.7,
            max_output_tokens=2048,
            convert_system_message_to_human=True
        )
        
        self.flash_model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.google_api_key,
            temperature=0.7,
            max_output_tokens=2048,
            convert_system_message_to_human=True
        )
        
        # Vision model is essentially the same class in LangChain, handled by input types
        self.vision_model = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro", # 1.5 Pro supports vision
            google_api_key=settings.google_api_key,
            temperature=0.4,
            max_output_tokens=2048
        )
    
    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_flash: bool = False
    ) -> str:
        """Generate text using Gemini Pro or Flash"""
        model = self.flash_model if use_flash else self.text_model
        
        # Override params if different from default (LangChain models are immutable-ish, so we clone or just use bind)
        # For simple usage, we can bind new config
        configured_model = model.bind(temperature=temperature, max_output_tokens=max_tokens)
        
        response = await configured_model.ainvoke(prompt)
        return response.content
    
    async def generate_text_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_flash: bool = False
    ) -> AsyncIterator[str]:
        """Stream text generation from Gemini"""
        model = self.flash_model if use_flash else self.text_model
        configured_model = model.bind(temperature=temperature, max_output_tokens=max_tokens)
        
        async for chunk in configured_model.astream(prompt):
            if chunk.content:
                yield chunk.content
    
    async def analyze_image(
        self,
        image_path: str | Path,
        prompt: str = "Provide a detailed scientific description of this image."
    ) -> str:
        """Analyze image using Gemini Vision via LangChain"""
        image_path = Path(image_path)
        
        # Read image file and encode
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
            
        mime_type = f"image/{image_path.suffix.lstrip('.')}"
        if mime_type == 'image/jpg': mime_type = 'image/jpeg'
        
        # Construct multimodal message
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_data}"}
                }
            ]
        )
        
        response = await self.vision_model.ainvoke([message])
        return response.content
    
    async def classify_intent(self, query: str) -> str:
        """Classify user intent for routing"""
        prompt = f"""Classify the following user query into ONE of these categories:
- SEARCH: User wants to find research papers
- DRAFT: User wants to write/generate academic text
- ANALYZE: User wants to analyze data/images
- CHAT: General question or discussion

Query: "{query}"

Return ONLY the category name, nothing else."""
        
        # Use Flash for speed
        result = await self.generate_text(prompt, temperature=0.1, use_flash=True)
        intent = result.strip().upper()
        
        if intent in ["SEARCH", "DRAFT", "ANALYZE", "CHAT"]:
            return intent
        return "CHAT"
    
    async def score_paper_relevance(
        self,
        paper_title: str,
        paper_abstract: str,
        query: str
    ) -> float:
        """Score paper relevance to query (0.0 to 1.0)"""
        prompt = f"""Rate how relevant this paper is to the user's query on a scale of 0.0 to 1.0.

Query: "{query}"

Paper Title: {paper_title}
Abstract: {paper_abstract}

Return ONLY a decimal number between 0.0 and 1.0, nothing else."""
        
        try:
            result = await self.generate_text(prompt, temperature=0.2, use_flash=True)
            score = float(result.strip())
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            return 0.5


# Global client instance
gemini_client = GeminiClient()
