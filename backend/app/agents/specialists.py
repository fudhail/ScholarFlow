"""Specialized Agent Implementations for ScholarFlow

This module contains individual specialized agents:
- CitationAgent: Manages citations, formats references, tracks sources
- MemoryAgent: Maintains conversation history and context
- SupervisorAgent: Coordinates between agents and makes routing decisions
- ResearchCoordinatorAgent: Manages search strategy and discovery workflow
- ProactiveAgent: Suggests next actions and improvements
- SynthesisAgent: Combines information from multiple sources

Enhanced with message bus for non-linear agent communication.
"""

from typing import Dict, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.core.ai_client import ai_client
from app.agents.state import ResearchState
from app.agents.message_bus import get_message_bus, MessageTopics, MessagePriority
import logging

logger = logging.getLogger(__name__)


# ===== CITATION AGENT =====

class CitationAgent:
    """
    Manages citations and references throughout the research process
    - Tracks all papers and their usage
    - Formats citations in requested style (IEEE, APA, etc.)
    - Suggests when to cite based on claims
    - Extracts page numbers from referenced text
    - Publishes citation events to message bus
    """
    
    def __init__(self):
        self.citation_style = "IEEE"  # Default
        self.citation_map = {}  # paper_id -> citation_number
        self.message_bus = get_message_bus()
        
        # Subscribe to citation requests
        self.message_bus.subscribe(MessageTopics.CITATION_NEEDED, self._handle_citation_request)
        
    async def _handle_citation_request(self, message):
        """Handle citation request from other agents via message bus"""
        payload = message.payload
        paper = payload.get('paper')
        if paper:
            citation = await self.generate_citation(paper)
            await self.message_bus.publish(
                from_agent="citation",
                topic=MessageTopics.CITATION_GENERATED,
                payload={"citation": citation, "paper_id": paper.get('id')}
            )
    
    async def generate_citation(
        self, 
        paper: Dict, 
        page_number: Optional[int] = None,
        text_snippet: Optional[str] = None
    ) -> str:
        """
        Generate formatted citation for a paper
        
        Args:
            paper: Paper dictionary with title, authors, year
            page_number: Optional page number for in-text citation
            text_snippet: Optional text being cited
            
        Returns:
            Formatted citation string
        """
        # Assign citation number if new paper
        paper_id = paper.get('id')
        if paper_id not in self.citation_map:
            self.citation_map[paper_id] = len(self.citation_map) + 1
        
        citation_num = self.citation_map[paper_id]
        
        # Publish citation generated event
        await self.message_bus.publish(
            from_agent="citation",
            topic=MessageTopics.CITATION_GENERATED,
            payload={"paper_id": paper_id, "citation_num": citation_num}
        )
        
        # Format based on style
        if self.citation_style == "IEEE":
            if page_number:
                return f"[{citation_num}, p.{page_number}]"
            return f"[{citation_num}]"
        elif self.citation_style == "APA":
            authors = paper.get('authors', [])
            year = paper.get('year', '')
            first_author = authors[0] if authors else 'Unknown'
            if page_number:
                return f"({first_author}, {year}, p. {page_number})"
            return f"({first_author}, {year})"
        
        return f"[{citation_num}]"
    
    async def suggest_citations(
        self, 
        text: str, 
        available_papers: List[Dict]
    ) -> List[Dict]:
        """
        Analyze text and suggest where citations are needed
        
        Returns list of suggestions with text span and recommended papers
        """
        prompt = f"""Analyze this text and identify claims that need citations:

TEXT:
{text}

AVAILABLE PAPERS:
{[p.get('title', '') for p in available_papers[:10]]}

For each claim needing a citation, return:
1. The specific claim text
2. Why it needs citation
3. Which paper(s) from the available list would support it

Return as structured list."""

        suggestions_text = await ai_client.generate_text(prompt, temperature=0.3)
        
        # Parse suggestions (simplified)
        return [{
            "text": text,
            "reason": "Factual claim",
            "suggested_papers": available_papers[:2]
        }]
    
    async def extract_page_from_context(
        self, 
        text_snippet: str, 
        paper_content: str
    ) -> Optional[int]:
        """
        Find which page a text snippet comes from
        
        This would integrate with the PDF processor to match text to pages
        """
        # Placeholder - would use PDF page tracking from vector store
        return None
    
    async def generate_bibliography(
        self, 
        used_papers: List[Dict]
    ) -> str:
        """Generate full bibliography/references section"""
        
        bibliography = []
        
        for i, paper in enumerate(used_papers, 1):
            title = paper.get('title', 'Untitled')
            authors = paper.get('authors', [])
            year = paper.get('year', 'n.d.')
            
            if self.citation_style == "IEEE":
                author_str = ', '.join(authors[:3])
                if len(authors) > 3:
                    author_str += ' et al.'
                entry = f"[{i}] {author_str}, \"{title},\" {year}."
            elif self.citation_style == "APA":
                author_str = ', '.join([f"{a.split()[-1]}, {a.split()[0][0]}." for a in authors[:7]])
                if len(authors) > 7:
                    author_str += ', et al.'
                entry = f"{author_str} ({year}). {title}."
            else:
                entry = f"{i}. {title}"
            
            bibliography.append(entry)
        
        return "\n".join(bibliography)


# ===== MEMORY AGENT =====

class MemoryAgent:
    """
    Maintains conversation history and contextual memory
    - Tracks research questions and their answers
    - Remembers user preferences and writing style
    - Provides relevant context from history
    - Summarizes long conversations
    """
    
    def __init__(self, max_memory_tokens: int = 4000):
        self.conversation_history: List[Dict] = []
        self.max_tokens = max_memory_tokens
        self.research_context = {
            "key_findings": [],
            "methodologies": [],
            "gaps_identified": []
        }
        
    async def add_interaction(
        self, 
        role: str, 
        content: str, 
        metadata: Optional[Dict] = None
    ):
        """Add a new interaction to memory"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": None  # Would use datetime
        })
        
        # Summarize if too long
        if len(self.conversation_history) > 20:
            await self._compress_history()
    
    async def _compress_history(self):
        """Compress old history into summary"""
        if len(self.conversation_history) < 10:
            return
        
        # Take first 15 messages to summarize
        to_summarize = self.conversation_history[:15]
        
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content'][:200]}"
            for msg in to_summarize
        ])
        
        prompt = f"""Summarize this research conversation, preserving key information:

{conversation_text}

Provide a concise summary highlighting:
- Main research questions
- Key findings discussed
- Papers referenced
- Decisions made"""

        summary = await ai_client.generate_text(prompt, temperature=0.3)
        
        # Replace old messages with summary
        self.conversation_history = [
            {"role": "system", "content": f"[Previous conversation summary]: {summary}"}
        ] + self.conversation_history[15:]
    
    async def retrieve_relevant_context(
        self, 
        current_query: str, 
        k: int = 5
    ) -> List[Dict]:
        """
        Retrieve most relevant past interactions for current query
        
        Uses semantic similarity (would integrate with vector store)
        """
        # Simplified - would use embeddings
        relevant = []
        query_lower = current_query.lower()
        
        for msg in reversed(self.conversation_history[-20:]):
            if any(word in msg['content'].lower() for word in query_lower.split()[:3]):
                relevant.append(msg)
                if len(relevant) >= k:
                    break
        
        return relevant
    
    async def extract_research_insights(self) -> Dict:
        """Extract key insights from conversation history"""
        
        recent_text = "\n".join([
            msg['content']
            for msg in self.conversation_history[-30:]
            if msg['role'] != 'system'
        ])
        
        if not recent_text:
            return self.research_context
        
        prompt = f"""Analyze this research conversation and extract:

1. Key findings or insights discovered
2. Research methodologies discussed
3. Gaps or questions identified

CONVERSATION:
{recent_text[:3000]}

Return structured insights."""

        insights_text = await ai_client.generate_text(prompt, temperature=0.4)
        
        # Parse and update context (simplified)
        return {
            "key_findings": ["Insight from conversation"],
            "methodologies": ["Method discussed"],
            "gaps_identified": ["Question to explore"]
        }


# ===== SUPERVISOR AGENT =====

class SupervisorAgent:
    """
    Coordinates between specialized agents
    - Decides which agent should handle a task
    - Manages workflow orchestration
    - Resolves conflicts between agents
    - Monitors progress and adjusts strategy
    """
    
    def __init__(self):
        self.active_agents = []
        self.task_queue = []
        
    async def route_request(
        self, 
        state: ResearchState
    ) -> Dict:
        """
        Analyze request and route to appropriate specialized agent(s)
        
        Returns routing decision with reasoning
        """
        query = state.get("query", "")
        selected_papers = state.get("selected_paper_ids", [])
        current_draft = state.get("current_draft", {})
        
        prompt = f"""You are the Supervisor Agent coordinating a research assistant system.

USER REQUEST: {query}

CONTEXT:
- Selected Papers: {len(selected_papers)}
- Current Draft Status: {current_draft.get('status', 'none')}

AVAILABLE AGENTS:
1. SearchAgent - Find and rank papers
2. CitationAgent - Manage citations and references
3. WriterAgent - Draft content
4. ReviewerAgent - Critique and improve drafts
5. LabAnalystAgent - Analyze data and figures
6. MemoryAgent - Retrieve past context

Decide which agent(s) should handle this request and in what order.
Consider: What's the primary intent? What information is needed? What's the optimal workflow?

Return: Primary agent, reasoning, and any secondary agents needed."""

        # OPTIMIZATION: The following LLM call takes ~10s and is unused because we use keyword routing below.
        # Commenting out to fix performance bottleneck.
        # routing = await ai_client.generate_text(prompt, temperature=0.3)
        routing = "Keyword-based routing applied for speed."
        
        # Parse routing decision (simplified)
        if "search" in query.lower() or "find" in query.lower():
            primary = "search"
        elif "cite" in query.lower() or "reference" in query.lower():
            primary = "citation"
        elif "write" in query.lower() or "draft" in query.lower():
            primary = "writer"
        elif "improve" in query.lower() or "revise" in query.lower():
            primary = "reviewer"
        else:
            primary = "writer"  # Default
        
        return {
            "primary_agent": primary,
            "secondary_agents": [],
            "reasoning": routing,
            "confidence": 0.8
        }
    
    async def monitor_progress(
        self, 
        state: ResearchState
    ) -> Dict:
        """
        Monitor workflow progress and suggest adjustments
        """
        logs = state.get("logs", [])
        iteration = state.get("search_iteration", 0)
        
        # Check for stuck workflows
        if iteration > 3:
            return {
                "status": "warning",
                "message": "Search refinement taking too long",
                "suggestion": "Consider broadening search terms or using different sources"
            }
        
        # Check for quality issues
        ranked_papers = state.get("ranked_papers", [])
        if ranked_papers and ranked_papers[0].get('relevance_score', ranked_papers[0].get('score', 0)) < 0.5:
            return {
                "status": "warning",
                "message": "Paper relevance scores are low",
                "suggestion": "User may want to refine their research question"
            }
        
        return {
            "status": "ok",
            "message": "Workflow progressing normally"
        }


# ===== PROACTIVE AGENT =====

class ProactiveAgent:
    """
    Suggests next actions and improvements proactively
    - Recommends relevant papers based on draft content
    - Suggests sections that need more support
    - Identifies missing citations
    - Proposes structural improvements
    """
    
    async def suggest_next_actions(
        self, 
        state: ResearchState
    ) -> List[Dict]:
        """Generate proactive suggestions for user"""
        
        suggestions = []
        
        # Check draft completeness
        current_draft = state.get("current_draft", {})
        if current_draft:
            content = current_draft.get("content", "")
            
            # Suggest citation checks
            if content and content.count("[") < 3:
                suggestions.append({
                    "type": "citation",
                    "priority": "high",
                    "message": "Your draft has few citations. Would you like me to suggest where to add references?",
                    "action": "analyze_citations"
                })
            
            # Suggest expanding sections
            if len(content.split("\n\n")) < 5:
                suggestions.append({
                    "type": "content",
                    "priority": "medium",
                    "message": "Consider expanding your draft with more detailed sections",
                    "action": "suggest_outline"
                })
        
        # Check for unused papers
        selected_papers = state.get("selected_paper_ids", [])
        if len(selected_papers) > 3 and not current_draft:
            suggestions.append({
                "type": "workflow",
                "priority": "high",
                "message": f"You have {len(selected_papers)} papers selected. Ready to generate a draft?",
                "action": "start_draft"
            })
        
        # Suggest related searches
        query = state.get("query", "")
        if query and not state.get("found_papers"):
            suggestions.append({
                "type": "search",
                "priority": "high",
                "message": "No papers found yet. Would you like me to broaden the search?",
                "action": "expand_search"
            })
        
        return suggestions
    
    async def analyze_draft_quality(
        self, 
        draft_text: str,
        selected_papers: List[Dict]
    ) -> Dict:
        """Analyze draft and provide improvement suggestions"""
        
        prompt = f"""Analyze this research draft and provide improvement suggestions:

DRAFT:
{draft_text[:2000]}

AVAILABLE PAPERS: {len(selected_papers)}

Analyze:
1. Structure and flow
2. Citation coverage (are claims supported?)
3. Depth of analysis
4. Areas needing expansion
5. Technical accuracy

Provide 3-5 specific, actionable suggestions."""

        analysis = await ai_client.generate_text(prompt, temperature=0.4)
        
        return {
            "overall_quality": "good",  # Would parse from analysis
            "suggestions": [
                {"area": "citations", "message": "Add more references to support claims"},
                {"area": "methodology", "message": "Expand methods section with more detail"}
            ],
            "detailed_feedback": analysis
        }


# ===== SYNTHESIS AGENT =====

class SynthesisAgent:
    """
    Combines information from multiple sources into coherent insights
    - Merges findings from multiple papers
    - Identifies patterns and trends
    - Resolves contradictions
    - Generates comparative analyses
    """
    
    async def synthesize_papers(
        self, 
        papers: List[Dict],
        focus_area: Optional[str] = None
    ) -> str:
        """
        Synthesize key insights from multiple papers
        """
        paper_summaries = "\n\n".join([
            f"Paper {i+1}: {p.get('title', 'Untitled')}\n{p.get('abstract', '')[:300]}"
            for i, p in enumerate(papers[:10])
        ])
        
        focus_instruction = f"\nFocus specifically on: {focus_area}" if focus_area else ""
        
        prompt = f"""Synthesize insights from these research papers:{focus_instruction}

{paper_summaries}

Provide:
1. Common themes and findings
2. Key methodologies used
3. Contradictions or disagreements
4. Gaps in current research
5. Overall state of the field

Be concise but comprehensive."""

        synthesis = await ai_client.generate_text(prompt, temperature=0.4, use_flash=True)
        return synthesis
    
    async def compare_papers(
        self, 
        papers: List[Dict],
        comparison_aspects: List[str] = None
    ) -> Dict:
        """
        Generate detailed comparison of papers
        """
        if not comparison_aspects:
            comparison_aspects = ["methodology", "findings", "limitations"]
        
        paper_info = "\n".join([
            f"{i+1}. {p.get('title', '')}: {p.get('abstract', '')[:200]}"
            for i, p in enumerate(papers[:5])
        ])
        
        prompt = f"""Compare these papers across: {', '.join(comparison_aspects)}

PAPERS:
{paper_info}

Create a comparison table highlighting similarities and differences."""

        comparison = await ai_client.generate_text(prompt, temperature=0.3, use_flash=True)
        
        return {
            "comparison_text": comparison,
            "aspects_compared": comparison_aspects,
            "paper_count": len(papers)
        }


# ===== RESEARCH COORDINATOR AGENT =====

class ResearchCoordinatorAgent:
    """
    Intelligent agent that manages the research discovery workflow
    - Evaluates search results quality
    - Decides search strategy (refine, expand, or proceed)
    - Determines when sufficient papers are found
    - Guides the research direction like a co-author
    - Provides reasoning for all decisions
    """
    
    def __init__(self):
        self.search_history = []
        self.quality_threshold = 0.7
        self.message_bus = get_message_bus()
        
    async def evaluate_search_results(
        self,
        query: str,
        found_papers: List[Dict],
        ranked_papers: List[Dict],
        iteration: int
    ) -> Dict:
        """
        Evaluate search results and decide next action
        
        Returns:
            decision: "proceed" | "refine_query" | "expand_search" | "try_different_approach"
            reasoning: Why this decision was made
            suggestions: Specific actions to take
        """
        
        num_papers = len(found_papers)
        num_relevant = len([
            p for p in ranked_papers
            if p.get('relevance_score', p.get('score', 0)) > self.quality_threshold
        ])
        avg_score = (
            sum([p.get('relevance_score', p.get('score', 0)) for p in ranked_papers]) / len(ranked_papers)
            if ranked_papers else 0
        )
        
        prompt = f"""You are a Research Coordinator making strategic decisions about a literature search.

SEARCH QUERY: "{query}"
ITERATION: {iteration} (max: 3)

RESULTS:
- Total papers found: {num_papers}
- Relevant papers (score >{self.quality_threshold}): {num_relevant}
- Average relevance score: {avg_score:.2f}

TOP 3 PAPERS:
{chr(10).join([f"{i+1}. {p.get('title', 'Unknown')} (score: {p.get('relevance_score', p.get('score', 0)):.2f})" for i, p in enumerate(ranked_papers[:3])])}

As an expert research coordinator, evaluate this search:

1. QUALITY ASSESSMENT: Are these results good enough?
   - Do we have sufficient high-quality papers (5-10)?
   - Are the top results truly relevant to the query?
   - Is there good diversity in approaches/perspectives?

2. DECISION: What should we do next?
   - "proceed": Results are good, move to analysis
   - "refine_query": Query is too broad/narrow, needs adjustment
   - "expand_search": Need more papers, try related terms
   - "try_different_approach": Current strategy isn't working

3. REASONING: Why this decision? (Think like a co-author guiding research)

4. SUGGESTIONS: Specific actions (e.g., "Focus on papers from 2020-2024", "Try 'RAG evaluation' instead")

Return: decision|reasoning|suggestions"""

        response = await ai_client.generate_text(prompt, temperature=0.4, use_flash=True)
        
        # Parse response
        parts = response.split('|')
        decision = parts[0].strip() if len(parts) > 0 else "proceed"
        reasoning = parts[1].strip() if len(parts) > 1 else "Results evaluated"
        suggestions = parts[2].strip() if len(parts) > 2 else ""
        
        # Publish decision to message bus
        await self.message_bus.publish(
            from_agent="research_coordinator",
            topic=MessageTopics.AGENT_DECISION,
            payload={
                "decision": decision,
                "reasoning": reasoning,
                "num_papers": num_papers,
                "num_relevant": num_relevant
            }
        )
        
        # Log decision
        logger.info(f"🧭 Research Coordinator: {decision.upper()} - {reasoning}")
        
        return {
            "decision": decision,
            "reasoning": reasoning,
            "suggestions": suggestions,
            "quality_metrics": {
                "total_papers": num_papers,
                "relevant_papers": num_relevant,
                "avg_score": avg_score,
                "iteration": iteration
            }
        }
    
    async def suggest_query_refinement(
        self,
        original_query: str,
        search_results: List[Dict],
        reason: str
    ) -> str:
        """
        Suggest an improved query based on results
        """
        
        prompt = f"""You are refining a search query that didn't produce optimal results.

ORIGINAL QUERY: "{original_query}"
PROBLEM: {reason}

CURRENT RESULTS (sample titles):
{chr(10).join([f"- {p.get('title', '')[:100]}" for p in search_results[:5]])}

As a research expert, suggest a refined query that will:
1. Be more specific if results were too broad
2. Use alternative terminology if results were too narrow
3. Add domain context if results were off-topic
4. Adjust time scope if results are outdated

Return ONLY the refined query, nothing else."""

        refined_query = await ai_client.generate_text(prompt, temperature=0.5, use_flash=True)
        
        return refined_query.strip().strip('"')
    
    async def assess_research_coverage(
        self,
        query: str,
        collected_papers: List[Dict]
    ) -> Dict:
        """
        Assess if we have sufficient coverage of the research topic
        """
        
        prompt = f"""Assess research coverage for this query: "{query}"

COLLECTED PAPERS: {len(collected_papers)}

KEY PAPER TOPICS:
{chr(10).join([f"- {p.get('title', '')}" for p in collected_papers[:10]])}

As a research advisor, assess:
1. Coverage score (0-10): How well do these papers cover the topic?
2. Gaps: What important aspects are missing?
3. Recommendation: Should we search for more papers or proceed?

Return: score|gaps|recommendation"""

        response = await ai_client.generate_text(prompt, temperature=0.4)
        parts = response.split('|')
        
        try:
            score = int(parts[0].strip()) if len(parts) > 0 else 7
        except:
            score = 7
        
        gaps = parts[1].strip() if len(parts) > 1 else "None identified"
        recommendation = parts[2].strip() if len(parts) > 2 else "Proceed with analysis"
        
        return {
            "coverage_score": score,
            "gaps": gaps,
            "recommendation": recommendation,
            "sufficient": score >= 7
        }


# ===== AGENT FACTORY =====

# Singleton instances
_citation_agent = None
_memory_agent = None
_supervisor_agent = None
_proactive_agent = None
_synthesis_agent = None
_research_coordinator_agent = None

def get_citation_agent() -> CitationAgent:
    global _citation_agent
    if _citation_agent is None:
        _citation_agent = CitationAgent()
    return _citation_agent

def get_memory_agent() -> MemoryAgent:
    global _memory_agent
    if _memory_agent is None:
        _memory_agent = MemoryAgent()
    return _memory_agent

def get_supervisor_agent() -> SupervisorAgent:
    global _supervisor_agent
    if _supervisor_agent is None:
        _supervisor_agent = SupervisorAgent()
    return _supervisor_agent

def get_proactive_agent() -> ProactiveAgent:
    global _proactive_agent
    if _proactive_agent is None:
        _proactive_agent = ProactiveAgent()
    return _proactive_agent

def get_synthesis_agent() -> SynthesisAgent:
    global _synthesis_agent
    if _synthesis_agent is None:
        _synthesis_agent = SynthesisAgent()
    return _synthesis_agent

def get_research_coordinator_agent() -> ResearchCoordinatorAgent:
    global _research_coordinator_agent
    if _research_coordinator_agent is None:
        _research_coordinator_agent = ResearchCoordinatorAgent()
    return _research_coordinator_agent
