"""Query analysis agent for understanding and expanding research queries"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict, List
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyzes user queries and generates optimized search strategies"""
    
    def __init__(self):
        """Initialize utilizing the global AI Client"""
        from app.core.ai_client import ai_client
        self.ai_client = ai_client
        
        self.ANALYSIS_PROMPT = """You are an expert academic research assistant. Your task is to analyze a user's query and generate a structured plan for searching academic databases.

**Instructions:**
1. **Analyze Context:** Read the provided history and the new user query to understand the user's true intent.
2. **Primary Query:** Formulate the best possible primary search query using precise, academic keywords.
3. **Expand Queries:** Generate 1-2 alternative or more specific queries that can be used if the primary query fails or to get diverse results.
4. **Chain of Thought:** Briefly explain your reasoning in a "thought" process.
5. **Output Format:** Return ONLY a valid JSON object with three keys: "thought", "search_query", and "expanded_queries" (a list of strings).

---
**Example:**
User Input: "how do RAG systems handle hallucinations?"

JSON Output:
{{
    "thought": "The user is asking about mitigation strategies for hallucinations in Retrieval-Augmented Generation. I will create a primary query focused on this mechanism.",
    "search_query": "Retrieval-Augmented Generation hallucination mitigation techniques",
    "expanded_queries": [
        "fact-checking in RAG pipelines",
        "improving factual consistency in large language models"
    ]
}}
---
**Conversation History:**
{history}

**User Input:**
{query}

**JSON Output:**
"""
    
    async def analyze_query(
        self,
        query: str,
        conversation_history: List[Dict] = None
    ) -> Dict[str, any]:
        """
        Analyze a research query and generate search strategies
        
        Args:
            query: User's research question
            conversation_history: Optional list of previous messages
        
        Returns:
            Dict with 'thought', 'search_query', and 'expanded_queries'
        """
        try:
            # Format conversation history
            history_text = ""
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages for context
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    history_text += f"{role.title()}: {content}\n"
            else:
                history_text = "No previous conversation."
            
            # Generate analysis using AI Client
            prompt = self.ANALYSIS_PROMPT.format(
                query=query,
                history=history_text
            )
            
            # Use Flash model for speed (works with Ollama or Gemini)
            response_text = await self.ai_client.generate_text(
                prompt, 
                temperature=0.1, 
                use_flash=True
            )
            
            # Parse JSON from response
            import json
            import re
            
            # Extract JSON block if wrapped in markdown
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find first { and last }
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end != 0:
                    json_str = response_text[start:end]
                else:
                    json_str = response_text
            
            try:
                result = json.loads(json_str)
                logger.info(f"✓ Query analysis successful:")
                logger.info(f"  Original query: {query}")
                logger.info(f"  Optimized query: {result.get('search_query', query)}")
                logger.info(f"  Expanded queries: {result.get('expanded_queries', [])}")
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse query analysis JSON: {response_text[:100]}...")
                # Fallback to simple structure
                return {
                    "thought": "Failed to parse AI analysis",
                    "search_query": query,
                    "expanded_queries": []
                }
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            return {
                "thought": "Error in query analysis, using original query",
                "search_query": query,
                "expanded_queries": []
            }


# Singleton instance
query_analyzer = QueryAnalyzer()
