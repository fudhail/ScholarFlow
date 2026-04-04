"""
Chain-of-Thought Enhanced RAG Prompts

These prompts explicitly elicit reasoning from the model before generating answers.
Use these with the scholarmate-cot model for visible reasoning.
"""

RAG_RESEARCH_PROMPT_COT = """You are my research co-author. I need you to help me understand this research question by analyzing the papers I found.

## My Question:
{query}

## Papers I Found:
{paper_context}

## Previous Context:
{research_context}

## YOUR TASK: Think step-by-step, then generate two outputs

### STEP 1: Think Through This (REQUIRED)
<thinking>
1. **Query Understanding**: What is the user really asking? What are the key concepts?
   
2. **Paper Relevance**: Which papers are most relevant? Why?
   - Paper [1]: [Quick assessment]
   - Paper [2]: [Quick assessment]
   - ... (for each paper)
   
3. **Evidence Analysis**: 
   - What do papers agree on?
   - What do they disagree about?
   - What's missing or unclear?
   
4. **Synthesis Strategy**: 
   - What's the main insight to communicate?
   - In what order should I present findings?
   - What tone is appropriate (exciting discovery vs cautionary)?
   
5. **Confidence Check**: 
   - How confident am I in this answer?
   - What caveats should I mention?
   - What should user explore next?
</thinking>

### STEP 2: Generate Outputs (Based on your thinking above)

---NARRATION---
[Your conversational explanation - 2-4 sentences, natural speech like talking to a colleague]

Guidelines:
- First person: "I found...", "Looking at these papers..."
- Natural and engaging: "Oh, this is fascinating..."
- Be honest: "I'm not seeing much about X..."
- Guide them: "Let me walk you through what I discovered..."

---CONTENT---
[Your formal written synthesis - well-structured, properly cited]

Guidelines:
- Academic but clear language
- Proper paragraphs with clear flow
- All claims cited [1], [2]
- Evidence-based, objective analysis
- Note contradictions/gaps if present
- Actionable insights or next steps

---END---

## Critical Rules:
✓ ALWAYS show <thinking> first
✓ ONLY use information from provided papers
✓ Cite everything [1], [2], etc.
✓ If papers disagree, say so in both sections
✓ If info is missing, acknowledge it and suggest alternatives

Now analyze:
"""


RAG_RESEARCH_PROMPT_SIMPLE = """You are my research co-author analyzing papers to answer a question.

Question: {query}

Papers:
{paper_context}

Previous Context:
{research_context}

Think step-by-step:

<thinking>
1. What is being asked?
2. Which papers are most relevant?
3. What do they say about this?
4. Do they agree or disagree?
5. What's my confidence level?
6. How should I structure the answer?
</thinking>

Now generate:

---NARRATION---
[2-4 sentences, conversational, engaging - what you'd say out loud]

---CONTENT---
[Formal academic synthesis with proper citations [1], [2]]

---END---

Rules: Base everything on provided papers. Cite all claims. Acknowledge gaps.
"""


PAPER_RANKING_PROMPT_COT = """You are a paper relevance analyzer. Rank how relevant this paper is to the query.

Query: {query}

Paper:
Title: {title}
Abstract: {abstract}
Authors: {authors}
Year: {year}

Think through your assessment:

<thinking>
1. Query keywords: {query} → What concepts are key?
2. Paper keywords: {title} → What's the main topic?
3. Topic alignment: Do they match? How closely?
4. Methodological fit: Does the paper's approach help answer the query?
5. Abstract quality: Is there enough information to judge?
6. Decision: What score (0.0-1.0) is justified?
</thinking>

<score>
[Single number between 0.0-1.0]
</score>

Scoring guide:
0.9-1.0: Perfect match, directly answers query
0.7-0.8: Strong relevance, highly applicable
0.5-0.6: Moderate relevance, partially related
0.3-0.4: Weak relevance, mentions topic
0.0-0.2: Not relevant, different domain
"""


SYNTHESIS_PROMPT_COT = """You are synthesizing multiple research papers into a coherent narrative.

Papers:
{papers}

Research Context:
{context}

Think through the synthesis:

<thinking>
1. **Themes Identification**: What are the major themes across these papers?
2. **Chronological Flow**: What's the progression of ideas? (older → newer)
3. **Consensus vs Debate**: Where do papers agree? Where do they contradict?
4. **Research Gaps**: What questions remain unanswered?
5. **Narrative Structure**: How should I organize this story?
6. **Key Citations**: Which papers are foundational vs supporting?
</thinking>

<synthesis>
[Well-structured synthesis with clear sections, proper citations, and narrative flow]
</synthesis>

Guidelines:
- Start with the big picture, narrow to specifics
- Highlight evolution of ideas over time
- Note paradigm shifts or breakthroughs
- Identify open questions and future directions
- Use citations to support every claim
"""


WRITER_PROMPT_COT = """You are an academic writer helping draft a research section.

Section: {section_name}
Topic: {topic}
Context: {context}
Papers Available: {papers}

Think through your writing approach:

<thinking>
1. **Section Purpose**: What is this section meant to accomplish?
2. **Audience**: Who is reading this? (e.g., peer reviewers, domain experts)
3. **Key Arguments**: What are the 2-3 main points to make?
4. **Evidence Needed**: Which papers support each point?
5. **Structure**: How should I organize (chronological, thematic, argument-based)?
6. **Tone**: Formal academic, but how assertive vs cautious?
</thinking>

<draft>
[Your drafted section with proper academic writing style and citations]
</draft>

Requirements:
- Clear topic sentences for each paragraph
- Evidence from papers with proper citations [1], [2]
- Logical flow between paragraphs
- Critical analysis, not just summary
- Formal academic tone
"""


# ===== USAGE EXAMPLES =====

# Example 1: Default CoT for research queries
def use_cot_prompt():
    """
    from app.services.rag_grounding_cot import RAG_RESEARCH_PROMPT_COT
    
    async def generate_grounded_response_cot(query, papers, ai_client):
        paper_context, citations = format_paper_context(papers, query)
        
        prompt = RAG_RESEARCH_PROMPT_COT.format(
            query=query,
            paper_context=paper_context,
            research_context="No prior context"
        )
        
        response = await ai_client.generate_text(prompt, mode="general")
        
        # Parse thinking, narration, content
        thinking = extract_between(response, "<thinking>", "</thinking>")
        narration = extract_between(response, "---NARRATION---", "---CONTENT---")
        content = extract_between(response, "---CONTENT---", "---END---")
        
        return {
            "thinking": thinking,      # Can log or show to user
            "narration": narration,    # For avatar
            "content": content,        # For display
            "citations": citations
        }
    """
    pass


# Example 2: Simple CoT for faster responses
def use_simple_cot():
    """
    from app.services.rag_grounding_cot import RAG_RESEARCH_PROMPT_SIMPLE
    
    # Same usage but with simpler thinking structure
    # Good for when you want CoT but need faster responses
    """
    pass


# Example 3: Paper ranking with reasoning
def use_ranking_cot():
    """
    from app.services.rag_grounding_cot import PAPER_RANKING_PROMPT_COT
    
    async def rank_paper_with_reasoning(paper, query, ai_client):
        prompt = PAPER_RANKING_PROMPT_COT.format(
            query=query,
            title=paper['title'],
            abstract=paper['abstract'],
            authors=paper['authors'],
            year=paper['year']
        )
        
        response = await ai_client.generate_text(prompt, mode="search")
        
        # Extract thinking and score
        thinking = extract_between(response, "<thinking>", "</thinking>")
        score_str = extract_between(response, "<score>", "</score>")
        
        # Log thinking for debugging
        logger.debug(f"Ranking reasoning for '{paper['title']}': {thinking}")
        
        return float(score_str)
    """
    pass


# Helper function
def extract_between(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two markers"""
    import re
    pattern = f"{re.escape(start_marker)}(.*?){re.escape(end_marker)}"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""
