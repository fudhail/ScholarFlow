"""RAG-Grounded Response Generation

This module ensures ALL responses are grounded in actual found papers,
with proper citations and no hallucination.

Supports Chain-of-Thought (CoT) reasoning when enabled in config.
"""

from typing import List, Dict, Optional, AsyncIterator
from dataclasses import dataclass
import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SourcedCitation:
    """A citation with its source paper"""
    index: int  # [1], [2], etc.
    title: str
    authors: str
    source: str  # ArXiv ID, DOI, etc.
    url: Optional[str] = None
    year: Optional[str] = None
    page: Optional[int] = None  # NEW: Page number for PDF jumps


def format_paper_context(papers: List[Dict], query: str) -> tuple[str, List[SourcedCitation]]:
    """
    Format found papers into context for the LLM with proper citation mapping.
    
    Returns:
        (formatted_context, citations_list)
    """
    if not papers:
        return "No relevant papers found.", []
    
    context_parts = []
    citations = []
    
    for idx, paper in enumerate(papers, 1):
        # Extract paper metadata
        title = paper.get("title", "Unknown Title")
        authors = paper.get("authors", "Unknown Authors")
        if isinstance(authors, list):
            authors = ", ".join(authors[:3])  # First 3 authors
            if len(paper.get("authors", [])) > 3:
                authors += " et al."
        
        abstract = paper.get("abstract", paper.get("summary", ""))
        
        # Check for page-specific text (from PDF chunks)
        text_content = paper.get("text") or abstract
        page_num = paper.get("page_number")
        
        source = paper.get("source", "Unknown")
        arxiv_id = paper.get("arxiv_id", paper.get("paperId", ""))
        url = paper.get("url", paper.get("pdf_url", ""))
        
        # safely extract year
        raw_year = paper.get("year") or paper.get("published")
        year = str(raw_year)[:4] if raw_year else ""
        
        # Create citation record
        citation = SourcedCitation(
            index=idx,
            title=title,
            authors=authors,
            source=f"{source}: {arxiv_id}" if arxiv_id else source,
            url=url,
            year=year,
            page=page_num  # Track page
        )
        citations.append(citation)
        
        # Format context entry with page info
        page_info = f" (Page {page_num})" if page_num else ""
        context_parts.append(f"""
[{idx}] **{title}**{page_info}
Authors: {authors} ({year})
Source: {citation.source}

Content: {text_content[:500]}{'...' if len(text_content) > 500 else ''}
""")
    
    formatted_context = "\n---\n".join(context_parts)
    return formatted_context, citations


def format_citations_reference(citations: List[SourcedCitation]) -> str:
    """Format citations as a reference list"""
    if not citations:
        return ""
    
    lines = ["\n\n## References\n"]
    seen_references = set()
    
    for c in citations:
        # Avoid duplicate reference entries in the list, though in text [1] vs [2] matters
        # If multiple chunks come from same paper, we might list it once
        # But for RAG grounded prompts, we usually map indices 1:1 to context blocks
        
        ref_key = f"{c.index}"
        if ref_key in seen_references:
            continue
        seen_references.add(ref_key)
        
        ref = f"[{c.index}] {c.authors}. \"{c.title}\""
        if c.year:
            ref += f" ({c.year})"
        if c.page:
            ref += f", p.{c.page}"  # Add page to reference
        if c.source:
            ref += f". {c.source}"
        if c.url:
            ref += f". {c.url}"
        lines.append(ref)
    
    return "\n".join(lines)


# ===== UTILITY: Parse Chain-of-Thought outputs =====

def parse_cot_response(response: str) -> Dict[str, str]:
    """Parse response with optional <thinking> tags and ---NARRATION--- / ---CONTENT--- markers
    
    Handles multiple marker variations:
    - ---NARRATION--- / ---CONTENT--- / ---END---
    - NARRATION / CONTENT markers
    - Natural section breaks
    
    Returns dict with keys: thinking, narration, content
    Falls back gracefully if tags are missing.
    """
    result = {
        "thinking": "",
        "narration": "",
        "content": ""
    }
    
    # Extract thinking (if present)
    thinking_match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL | re.IGNORECASE)
    if thinking_match:
        result["thinking"] = thinking_match.group(1).strip()
        # Remove thinking from response for further parsing
        response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL | re.IGNORECASE)
    
    # Try parsing with strict markers first: ---NARRATION--- / ---CONTENT---
    if "---NARRATION---" in response and "---CONTENT---" in response:
        parts = response.split("---NARRATION---")
        if len(parts) > 1:
            rest = parts[1].split("---CONTENT---")
            if len(rest) > 1:
                result["narration"] = rest[0].strip()
                result["content"] = rest[1].split("---END---")[0].strip()
                return result
    
    # Try parsing with looser markers: "NARRATION" / "CONTENT" (with newlines)
    narration_match = re.search(
        r'(?:###?\s+)?(?:\*\*)?(?:AVATAR\s+)?NARRATION(?:\*\*)?[:\s]+(.*?)(?=(?:###?\s+)?(?:\*\*)?CONTENT|\Z)',
        response,
        re.DOTALL | re.IGNORECASE
    )
    content_match = re.search(
        r'(?:###?\s+)?(?:\*\*)?CONTENT(?:\*\*)?[:\s]+(.*?)(?=##|References:|\Z)',
        response,
        re.DOTALL | re.IGNORECASE
    )
    
    if narration_match:
        result["narration"] = narration_match.group(1).strip()
    
    if content_match:
        result["content"] = content_match.group(1).strip()
    
    # Fallback: if we only got partial parsing, try to intelligently split
    if not result["narration"] and not result["content"]:
        # Last resort: just use entire response
        result["content"] = response.strip()
        result["narration"] = "Here's what I found in the research."
    elif not result["content"] and result["narration"]:
        # If only got narration, rest is content
        result["content"] = response.replace(result["narration"], "").strip()
    elif not result["narration"] and result["content"]:
        # If only got content, use first 2 sentences as narration
        sentences = re.split(r'(?<=[.!?])\s+', result["content"][:200])
        result["narration"] = ". ".join(sentences[:2]) + "."
    
    return result


# RAG-Grounded Prompt Templates (Dual Output: Narration + Written Content)
# These prompts work with or without CoT - the model will add <thinking> if trained to do so
RAG_RESEARCH_PROMPT = """You are ScholarFlow's research-grounded assistant.

## User Question
{query}

## Retrieved Sources
{paper_context}

## Previous Research Context
{research_context}

## Goal
Produce a factual, source-grounded answer that is easy to scan and verify.

Output EXACTLY in this format:

## NARRATION
[2-3 conversational sentences describing what you concluded from the papers. Keep it short and non-repetitive.]

## CONTENT
### Direct Answer
[2-5 concise sentences answering the question. Every factual claim must include citation markers like [1], [2].]

### Evidence
- [Claim 1 with citation(s)]
- [Claim 2 with citation(s)]
- [If sources disagree, include one contradiction bullet with citations]

### Confidence
[One line: High / Medium / Low and a brief reason based on source quality/coverage]

### Gaps
[One short bullet list of unknowns or missing evidence from the provided papers]

## Hard Rules
1. Use ONLY retrieved papers; do not add outside facts.
2. No repeated paragraphs, no filler text.
3. If evidence is insufficient, say so explicitly.
4. Keep the response concise and practical.
"""


RAG_SUMMARY_PROMPT = """Summarize the retrieved papers in a citation-first format.

## Question
{query}

## Papers
{paper_context}

Output EXACTLY in this format:

## NARRATION
[1-2 concise sentences introducing what was found.]

## CONTENT
### Summary
[A short paragraph with only source-grounded claims and citations]

### Agreement
- [Point of agreement with citations]

### Disagreement
- [Point of disagreement with citations or state "No major disagreement found"]

### Research Gaps
- [Missing evidence or unresolved question]

Rules:
1. Every claim must include [n] citations.
2. No external knowledge.
3. Keep the answer concise and non-repetitive.
"""


async def generate_grounded_response(
    query: str,
    papers: List[Dict],
    ai_client,
    prompt_type: str = "research",
    research_context: Optional[str] = None  # NEW: Unified memory context
) -> Dict:
    """
    Generate a response grounded in the provided papers.
    
    Returns dict with:
        - narration: What the avatar says (conversational)
        - content: Written content (formal)
        - response: Full response (for backwards compatibility)
        - citations: List of SourcedCitation objects
        - papers_used: List of paper IDs that should be saved
    """
    # Format papers into context
    paper_context, citations = format_paper_context(papers, query)
    
    # Select prompt template
    if prompt_type == "summary":
        prompt = RAG_SUMMARY_PROMPT.format(query=query, paper_context=paper_context)
    else:
        prompt = RAG_RESEARCH_PROMPT.format(
            query=query, 
            paper_context=paper_context,
            research_context=research_context or "No relevant past context found."
        )
    
    # Generate response using streaming for faster initial response
    # Even though we accumulate the full response, streaming starts returning tokens immediately
    response = ""
    chunk_count = 0
    try:
        async for chunk in ai_client.generate_text_stream(prompt, temperature=0.3, use_flash=True):
            response += chunk
            chunk_count += 1
            # Log progress every 50 chunks for debugging
            if chunk_count % 50 == 0:
                logger.debug(f"Generated {chunk_count} chunks, {len(response)} chars so far...")
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        response = ""
    
    logger.info(f"Response generation complete: {len(response)} chars from {chunk_count} chunks")
    
    if not response:
        logger.warning(f"AI Client returned empty response for query: {query}")
        return {
            "thinking": "",
            "narration": "I apologize, but I was unable to generate a response at this time. Please try again.",
            "content": "",
            "response": "I apologize, but I was unable to generate a response at this time. Please try again.",
            "citations": citations,
            "papers_used": [],
            "total_papers_found": len(papers)
        }

    # Parse response (handles both CoT with <thinking> and standard format)
    parsed = parse_cot_response(response)
    thinking = parsed["thinking"]
    narration = parsed["narration"]
    content = parsed["content"]
    
    # Log parsing results for debugging
    logger.info(f"Response parsing: narration_length={len(narration)}, content_length={len(content)}, has_thinking={bool(thinking)}")
    if narration:
        logger.debug(f"Extracted narration: {narration[:150]}...")
    else:
        logger.warning(f"No narration extracted. Response length: {len(response)}. First 200 chars: {response[:200]}")
    
    # Log thinking if present (for debugging/analysis)
    if thinking:
        logger.info(f"Model reasoning: {thinking[:200]}...")  # Log first 200 chars
    
    # Append reference list to content only
    references = format_citations_reference(citations)
    full_content = content + references
    
    # Extract which papers were actually used (by looking for [1], [2] in content)
    papers_used = []
    
    # Include thinking in return value (can be logged or shown to user)
    # Frontend can decide whether to display it based on settings.show_thinking_to_user
    for c in citations:
        if f"[{c.index}]" in content:
            papers_used.append({
                "title": c.title,
                "authors": c.authors,
                "source": c.source,
                "url": c.url
            })
    
    return {
        "thinking": thinking,      # Chain-of-Thought reasoning (may be empty)
        "narration": narration,    # What avatar says
        "content": full_content,   # What's displayed
        "response": full_content,  # Backwards compatibility
        "citations": citations,
        "papers_used": papers_used,
        "total_papers_found": len(papers)
    }


async def stream_grounded_response(
    query: str,
    papers: List[Dict],
    ai_client,
    prompt_type: str = "research",
    research_context: Optional[str] = None
) -> AsyncIterator[Dict]:
    """
    Stream a response grounded in the provided papers token-by-token.
    
    Yields dicts with:
        - type: "chunk" | "metadata"
        - content: text chunk (for type="chunk")
        - citations: list (for type="metadata")
        - papers_used: list (for type="metadata")
    """
    # Format papers into context
    paper_context, citations = format_paper_context(papers, query)
    
    # Select prompt template
    if prompt_type == "summary":
        prompt = RAG_SUMMARY_PROMPT.format(query=query, paper_context=paper_context)
    else:
        prompt = RAG_RESEARCH_PROMPT.format(
            query=query, 
            paper_context=paper_context,
            research_context=research_context or "No relevant past context found."
        )
    
    # Stream response chunks
    full_response = ""
    try:
        async for chunk in ai_client.generate_text_stream(prompt, temperature=0.3, use_flash=True):
            full_response += chunk
            yield {
                "type": "chunk",
                "content": chunk
            }
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        yield {
            "type": "chunk",
            "content": "I apologize, but I encountered an error while generating the response."
        }
        return
    
    # Append reference list at the end
    references = format_citations_reference(citations)
    if references:
        yield {
            "type": "chunk",
            "content": references
        }
    
    # Extract which papers were actually used
    papers_used = []
    for c in citations:
        if f"[{c.index}]" in full_response:
            papers_used.append({
                "title": c.title,
                "authors": c.authors,
                "source": c.source,
                "url": c.url
            })
    
    # Send metadata at the end
    yield {
        "type": "metadata",
        "citations": citations,
        "papers_used": papers_used,
        "total_papers_found": len(papers)
    }
