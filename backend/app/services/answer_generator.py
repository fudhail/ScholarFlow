"""Research answer generation with structured output"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import List, Dict, Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class StructuredAnswerGenerator:
    """Generates structured research answers from paper context"""
    
    def __init__(self):
        """Initialize the answer generator with Gemini"""
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",  # Fast model for research
            # temperature=0.1,  # Removed to fix unexpected keyword argument error
            google_api_key=settings.google_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_template(
            """You are a careful research assistant specialized in academic literature analysis. 
Using ONLY the provided context (research paper excerpts and metadata), produce a precise, 
evidence-focused answer to the user's question.

**Output Requirements:**
Generate a JSON response with the following fields:

1. **summary**: A 2-4 sentence concise summary answering the question directly, grounded in the provided context. Include inline citations like (Author, Year).

2. **key_points**: The top 3-5 evidence-backed bullet points (each 1-2 sentences) with brief citations in parentheses. Focus on the most important findings.

3. **recommended_actions**: Up to 5 practical next steps the user could take:
   - Read specific papers or review articles
   - Explore particular methodologies or datasets
   - Investigate related research areas
   - Run experiments or replicate results

4. **explanation_steps**: A short step-by-step description (3-6 items) of what you did to arrive at the answer:
   - Example: "Searched for recent transformer-based models"
   - Example: "Extracted evaluation metrics from 3 papers"
   - Example: "Identified common limitations across studies"

5. **confidence**: One of ['low', 'medium', 'high'] indicating how well the context supports the answer:
   - high: Context directly answers the question with strong evidence
   - medium: Context partially answers or requires some inference
   - low: Context is tangentially related or insufficient

6. **notes**: Optional clarification or caveat if the context was limited or if there are conflicting findings.

**Critical Rules:**
- Use ONLY facts present in the context
- If the context lacks evidence, state this clearly - never fabricate
- Always cite sources when making claims (Author, Year)
- Keep all text concise and factual
- If papers disagree, acknowledge the disagreement

**Context from Research Papers:**
{context}

**User's Question:**
{question}

Generate a thorough, scholarly response grounded in the evidence."""
        )
        
        # Define JSON schema for structured output
        self.json_schema = {
            "title": "StructuredResearchAnswer",
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "2-4 sentence answer summary with citations"
                },
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 evidence-backed bullet points with citations"
                },
                "recommended_actions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Up to 5 practical next steps"
                },
                "explanation_steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-6 step description of the research process"
                },
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Confidence level in the answer"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional caveats or clarifications"
                }
            },
            "required": ["summary", "key_points", "recommended_actions", "explanation_steps", "confidence"]
        }
        
        # Create structured output chain
        self.structured_llm = self.llm.with_structured_output(self.json_schema)
        self.chain = self.prompt | self.structured_llm
    
    async def generate_answer(
        self,
        question: str,
        context_chunks: List[str],
        paper_metadata: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Generate a structured answer from paper context
        
        Args:
            question: User's research question
            context_chunks: Retrieved text chunks from papers
            paper_metadata: Optional metadata about source papers (title, authors, year)
        
        Returns:
            Structured answer dictionary
        """
        try:
            if settings.mock_ai_responses:
                # MOCK IMPLEMENTATION - Bypass real API
                logger.info(f"MOCK MODE: Generating answer for '{question}'")
                import asyncio
                await asyncio.sleep(1.0)
                
                return {
                    "summary": "This is a MOCK ANSWER generated because the system is running in Mock Mode (enabled in config). The system has found relevant papers (mocked) and is simulating the response. To rely on real AI generation, set MOCK_AI_RESPONSES=False in environment variables.",
                    "key_points": [
                        "The system is currently running in full mock mode.",
                        "No external API calls to Google Gemini are being made.",
                        "The workflow steps (analysis, search, ranking, generation) are all simulated.",
                        "You can test the UI responsiveness and data flow without incurring costs."
                    ],
                    "recommended_actions": [
                        "Check your Google API Quota in the Cloud Console",
                        "Switch to a paid plan or wait for the free quota to reset",
                        "Disable MOCK_AI_RESPONSES in .env to use real API"
                    ],
                    "explanation_steps": [
                        "Received user query",
                        "Simulated paper search and retrieval",
                        "By-passed LLM generation due to mock mode",
                        "Returns structured mock response"
                    ],
                    "confidence": "high",
                    "notes": "System is functioning correctly in mock mode."
                }
            
            else:
                # REAL IMPLEMENTATION
                # Format context with metadata if available
                formatted_context = self._format_context(context_chunks, paper_metadata)
                
                # Generate structured answer
                result = await self.chain.ainvoke({
                    "question": question,
                    "context": formatted_context
                })
                
                logger.info(f"Generated structured answer for: {question[:50]}...")
                return result
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                "summary": "Unable to generate answer due to an error.",
                "key_points": [],
                "recommended_actions": [],
                "explanation_steps": [],
                "confidence": "low",
                "notes": f"Error: {str(e)}"
            }
    
    def _format_context(
        self,
        chunks: List[str],
        metadata: Optional[List[Dict]] = None
    ) -> str:
        """Format context chunks with paper metadata"""
        if not chunks:
            return "No context available."
        
        formatted_parts = []
        
        # Add metadata summary if available
        if metadata:
            formatted_parts.append("**Available Papers:**")
            for i, paper in enumerate(metadata[:10], 1):  # Limit to 10
                title = paper.get('title', 'Unknown')
                authors = paper.get('authors', ['Unknown'])
                year = paper.get('year', 'Unknown')
                
                # Format author list
                if isinstance(authors, list):
                    author_str = authors[0] if authors else 'Unknown'
                    if len(authors) > 1:
                        author_str += ' et al.'
                else:
                    author_str = authors
                
                formatted_parts.append(f"{i}. {title} ({author_str}, {year})")
            
            formatted_parts.append("\n**Relevant Excerpts:**")
        
        # Add chunks
        for i, chunk in enumerate(chunks[:10], 1):  # Limit to 10 chunks
            formatted_parts.append(f"\n[Excerpt {i}]\n{chunk}\n")
        
        return "\n".join(formatted_parts)


# Singleton instance
answer_generator = StructuredAnswerGenerator()
