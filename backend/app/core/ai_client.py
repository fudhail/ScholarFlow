"""Unified AI client for Multi-Provider LLM Support (Gemini, Ollama, OpenAI)"""

from typing import AsyncIterator, Optional, List
from pathlib import Path
import base64
import logging

# LangChain Imports
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Optional providers (only import if available)
try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    ChatOllama = None

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    ChatOpenAI = None

from .config import settings

logger = logging.getLogger(__name__)

class AIClient:
    """Singleton client for AI Model interactions (Text & Vision)"""
    
    _instance: Optional['AIClient'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize models based on configured provider"""
        self.provider = settings.llm_provider.lower()
        logger.info(f"Initializing AI Client with provider: {self.provider}")
        
        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "ollama":
            self._init_ollama()
        elif self.provider == "hybrid":
            self._init_hybrid()
        elif self.provider == "openai":
            self._init_openai()
        else:
            logger.warning(f"Unknown provider '{self.provider}', falling back to Gemini")
            self._init_gemini()
    
    def _init_hybrid(self):
        """Initialize Hybrid Mode: Ollama for text, Gemini for vision"""
        logger.info("Initializing Hybrid Mode (Ollama + Gemini)")
        
        # Initialize Ollama for text generation
        if OLLAMA_AVAILABLE:
            base_url = settings.ollama_base_url
            
            self.text_model = ChatOllama(
                model=settings.ollama_model_smart,  # scholarmate
                base_url=base_url,
                temperature=0.3,  # Lower for academic precision
                keep_alive=-1  # Keep model in memory indefinitely
            )
            self.flash_model = ChatOllama(
                model=settings.ollama_model_fast,  # llama3.2:1b
                base_url=base_url,
                temperature=0.7,  # Higher for faster sampling
                keep_alive=-1  # Keep model in memory indefinitely
            )
            
            # Specialized model for research mode (paper relevance scoring)
            self.search_model = ChatOllama(
                model=settings.ollama_model_search,  # scholarflow-search
                base_url=base_url,
                temperature=0.2,  # Deterministic scoring
                keep_alive=-1
            )
            
            # Specialized model for studio mode (original academic writing)
            self.studio_model = ChatOllama(
                model=settings.ollama_model_studio,  # scholarflow-studio
                base_url=base_url,
                temperature=0.75,  # Creative but controlled
                keep_alive=-1
            )
            
            logger.info(f"Ollama models initialized: {settings.ollama_model_smart} (smart), {settings.ollama_model_fast} (fast), {settings.ollama_model_search} (search), {settings.ollama_model_studio} (studio)")
        else:
            logger.warning("Ollama not available, using Gemini for all tasks")
            self._init_gemini()
            return
        
        # Initialize Gemini for vision tasks
        api_key = settings.google_api_key
        self.vision_model = ChatGoogleGenerativeAI(
            model=settings.vision_model_name,
            google_api_key=api_key,
            convert_system_message_to_human=True
        )
        logger.info(f"Gemini vision model initialized: {settings.vision_model_name}")
        
        # Store reference to Gemini for fallback
        self.gemini_fallback = ChatGoogleGenerativeAI(
            model=settings.fast_model_name,
            google_api_key=api_key,
            convert_system_message_to_human=True
        )

    def _init_gemini(self):
        """Initialize Google Gemini Models"""
        api_key = settings.google_api_key
        
        self.text_model = ChatGoogleGenerativeAI(
            model=settings.text_model_name,
            google_api_key=api_key,
            # temperature=0.7,  # Removed to fix API error
            # max_output_tokens=2048,  # Removed to fix API error
            convert_system_message_to_human=True
        )
        self.flash_model = ChatGoogleGenerativeAI(
            model=settings.fast_model_name,
            google_api_key=api_key,
            # temperature=0.7,  # Removed to fix API error
            # max_output_tokens=2048,  # Removed to fix API error
            convert_system_message_to_human=True
        )
        # Gemini Pro supports vision natively
        self.vision_model = self.text_model

    def _init_ollama(self):
        """Initialize Ollama Models (Local)"""
        if not OLLAMA_AVAILABLE:
            logger.error("Ollama provider requested but langchain_ollama not installed. Falling back to Gemini.")
            self._init_gemini()
            return
        base_url = settings.ollama_base_url or "http://localhost:11434"
        
        self.text_model = ChatOllama(
            model=settings.ollama_model_smart,
            base_url=base_url,
            temperature=0.3,
            keep_alive=-1
        )
        self.flash_model = ChatOllama(
            model=settings.ollama_model_fast,
            base_url=base_url,
            temperature=0.7,
            keep_alive=-1
        )
        self.search_model = ChatOllama(
            model=settings.ollama_model_search,
            base_url=base_url,
            temperature=0.2,
            keep_alive=-1
        )
        self.studio_model = ChatOllama(
            model=settings.ollama_model_studio,
            base_url=base_url,
            temperature=0.75,
            keep_alive=-1
        )
        # Vision requires a vision-capable key like 'llava'
        self.vision_model = ChatOllama(
            model=settings.vision_model_name, # e.g., "llava"
            base_url=base_url,
            temperature=0.4
        )

    def _init_openai(self):
        """Initialize OpenAI Compatible Models (vLLM, Groq, OpenAI)"""
        if not OPENAI_AVAILABLE:
            logger.error("OpenAI provider requested but langchain_openai not installed. Falling back to Gemini.")
            self._init_gemini()
            return
        base_url = getattr(settings, 'openai_base_url', None)  # Can be None for official OpenAI
        
        self.text_model = ChatOpenAI(
            model=settings.text_model_name,
            base_url=base_url,
            api_key=settings.google_api_key, # Using same key var for convenience, or add openai_api_key
            temperature=0.7
        )
        self.flash_model = ChatOpenAI(
            model=settings.fast_model_name,
            base_url=base_url,
            api_key=settings.google_api_key,
            temperature=0.7
        )
        self.vision_model = ChatOpenAI(
            model=settings.vision_model_name, # e.g. gpt-4-vision
            base_url=base_url,
            api_key=settings.google_api_key,
            temperature=0.4
        )


    async def generate_text(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_flash: bool = True,
        mode: str = "general"  # "general", "search", "studio"
    ) -> str:
        """Generate text using either mock or real model
        
        Args:
            prompt: The prompt to generate text from
            temperature: Temperature for generation (overridden by mode defaults)
            max_tokens: Max tokens to generate
            use_flash: Use fast model (overrides mode selection)
            mode: Operation mode - "general", "search" (research/ranking), "studio" (academic writing)
        """
        import time
        
        start = time.time()
        
        if settings.mock_ai_responses:
            """Generate text using MOCK responses (no API calls)"""
            import asyncio
            await asyncio.sleep(0.5)  # Small delay for realism
            
            # Return context-aware mock responses
            if "chain" in prompt.lower() and "thought" in prompt.lower():
                return """Chain-of-Thought (CoT) prompting significantly improves the reasoning capabilities of Large Language Models (LLMs) by encouraging them to generate intermediate reasoning steps before arriving at a final answer. This technique mimics human problem-solving processes.

Key findings from the research:
- CoT enables models to decompose complex problems into manageable intermediate steps
- Performance gains are substantial on reasoning benchmarks like GSM8K and arithmetic tasks
- This is an emergent property that typically appears in models with 100B+ parameters
- The approach serves as a bridge for reasoning, allowing models to "think" before they "speak"

The effectiveness of CoT is highly dependent on the quality of the reasoning demonstrations provided in the prompt."""
            elif "analyze" in prompt.lower() or "intent" in prompt.lower():
                return "CHAT"  # Default intent
            else:
                return "This is a mock response for testing. The actual AI client is disabled to avoid quota limits."
        
        else:
            # REAL IMPLEMENTATION - Select model based on mode
            if use_flash:
                model = self.flash_model
                model_name = "flash"
            elif mode == "search":
                model = self.search_model  # scholarflow-search (1B, optimized for ranking)
                model_name = "search"
            elif mode == "studio":
                model = self.studio_model  # scholarflow-studio (3B, optimized for writing)
                model_name = "studio"
            else:
                model = self.text_model  # Default: scholarmate
                model_name = "smart"
            
            # Bind runtime params - temperature and max_tokens removed to fix API error
            try:
               configured = model  # Use model directly without bind
            except:
               configured = model
    
            # Try Ollama with fallback to Gemini on failure
            try:
                response = await configured.ainvoke(prompt)
                elapsed = time.time() - start
                logger.info(f"Generation ({model_name} model, mode={mode}) took {elapsed:.2f}s")
                return response.content
            except Exception as e:
                logger.error(f"Ollama model failed ({model_name}): {e}. Falling back to Gemini.")
                if hasattr(self, 'gemini_fallback'):
                    try:
                        response = await self.gemini_fallback.ainvoke(prompt)
                        elapsed = time.time() - start
                        logger.warning(f"Gemini fallback succeeded after {elapsed:.2f}s")
                        return response.content
                    except Exception as fallback_error:
                        logger.error(f"Gemini fallback also failed: {fallback_error}")
                        raise Exception(f"Both primary and fallback models failed: {e}")
                else:
                    raise Exception(f"Primary model failed and no fallback available: {e}")

    async def generate_text_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_flash: bool = True
    ) -> AsyncIterator[str]:
        """Stream text generation"""
        if settings.mock_ai_responses:
            """Stream MOCK text generation"""
            import asyncio
            mock_response = await self.generate_text(prompt, temperature, max_tokens, use_flash)
            
            # Stream word by word
            words = mock_response.split()
            for word in words:
                await asyncio.sleep(0.05)
                yield word + " "
        else:
            # REAL IMPLEMENTATION
            model = self.flash_model if use_flash else self.text_model
            try:
               configured = model  # Use model directly without bind
            except:
               configured = model
    
            try:
                async for chunk in configured.astream(prompt):
                    content = chunk.content
                    if content:
                        yield content
            except Exception as e:
                logger.error(f"Streaming failed: {e}. Falling back to non-streaming.")
                # Fallback to non-streaming generation
                result = await self.generate_text(prompt, temperature, max_tokens, use_flash)
                yield result

    async def analyze_image(
        self,
        image_path: str | Path,
        prompt: str = "Provide a detailed scientific description of this image."
    ) -> str:
        """Multimodal image analysis"""
        if settings.mock_ai_responses:
            """MOCK image analysis (no API calls)"""
            import asyncio
            await asyncio.sleep(0.3)
            return "This is a mock image analysis. The image appears to contain scientific or experimental data. Actual analysis is disabled to avoid API quota limits."
            
        else:
            # REAL IMPLEMENTATION
            image_path = Path(image_path)
            
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
                
            mime_type = f"image/{image_path.suffix.lstrip('.')}"
            if mime_type == 'image/jpg': mime_type = 'image/jpeg'
            
            from langchain_core.messages import HumanMessage
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
        if settings.mock_ai_responses:
            """MOCK intent classification"""
            import asyncio
            await asyncio.sleep(0.2)
            
            # Simple keyword based mock routing
            q_lower = query.lower()
            if "draft" in q_lower or "write" in q_lower or "outline" in q_lower:
                return "DRAFT"
            if "analyze" in q_lower and ("image" in q_lower or "figure" in q_lower or "data" in q_lower):
                return "ANALYZE"
                
            return "SEARCH"  # Default to SEARCH for RAG-based research
            
        else:
            # REAL IMPLEMENTATION
            prompt = f"""Classify the following user query into ONE of these categories:
- SEARCH: User is asking a research question or wants to learn about a topic (DEFAULT for knowledge queries)
- DRAFT: User explicitly wants to write/generate/compose academic text or a manuscript section
- ANALYZE: User wants to analyze uploaded images, figures, or lab data

Query: "{query}"

IMPORTANT: For any knowledge or research question (e.g., "what is...", "how does...", "explain..."), classify as SEARCH.
Only use DRAFT if the user explicitly asks to write or draft something.

Return ONLY the category name, nothing else."""
            
            # Use Flash for speed
            result = await self.generate_text(prompt, temperature=0.1, use_flash=True)
            intent = result.strip().upper()
            
            if any(cat in intent for cat in ["SEARCH", "DRAFT", "ANALYZE"]):
                if "DRAFT" in intent: return "DRAFT"
                if "ANALYZE" in intent: return "ANALYZE"
                if "SEARCH" in intent: return "SEARCH"
                
            # Default to SEARCH for RAG-based research assistant
            return "SEARCH"

    async def score_paper_relevance(
        self,
        paper_title: str,
        paper_abstract: str,
        query: str
    ) -> float:
        """Score paper relevance using specialized search model (optimized for fast, accurate ranking)"""
        if settings.mock_ai_responses:
            """MOCK paper scoring"""
            import random
            # Return high scores for mock papers to ensure they pass filters
            return 0.85 + (random.random() * 0.1)
            
        else:
            # REAL IMPLEMENTATION - Use search model for fast relevance scoring
            prompt = f"""Rate how relevant this paper is to the user's query on a scale of 0.0 to 1.0.

Query: "{query}"
Paper Title: {paper_title}
Abstract: {paper_abstract}

Return ONLY a decimal number between 0.0 and 1.0."""
            
            try:
                # Use search mode for optimized relevance scoring
                result = await self.generate_text(prompt, temperature=0.2, use_flash=True, mode="search")
                # Cleanup potential non-numeric chars
                clean_result = ''.join(c for c in result if c.isdigit() or c == '.')
                score = float(clean_result)
                return max(0.0, min(1.0, score))
            except (ValueError, TypeError) as e:
                logger.warning(f"Score parsing failed: {e}. Returning default 0.5")
                return 0.5
            except Exception as e:
                logger.error(f"Relevance scoring failed: {e}. Returning default 0.5")
                return 0.5

    async def generate_batch(
        self,
        prompts: List[str],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_flash: bool = False,
        mode: str = "general"
    ) -> List[str]:
        """Generate multiple responses in parallel for faster multi-agent workflows"""
        import asyncio
        import time
        
        start = time.time()
        
        tasks = [
            self.generate_text(prompt, temperature, max_tokens, use_flash, mode=mode)
            for prompt in prompts
        ]
        
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        logger.info(f"Batch generation ({len(prompts)} prompts) took {elapsed:.2f}s ({elapsed/len(prompts):.2f}s avg)")
        
        return results

# Global client instance
ai_client = AIClient()
