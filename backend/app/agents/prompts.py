"""Section-aware prompts for academic writing"""

# Academic section templates with context-aware instructions
SECTION_PROMPTS = {
    "introduction": {
        "name": "Introduction",
        "template": """You are writing the INTRODUCTION section of an academic research paper.

CONTEXT FROM LITERATURE:
{literature_context}

USER REQUEST: {query}

INSTRUCTIONS:
1. Start with broad background on the research area
2. Narrow to the specific problem or research gap
3. Briefly preview YOUR contribution (the student's work)
4. End with paper structure overview if appropriate

TONE: Scholarly, measured, confident but not overclaimed
CITATIONS: Heavy use of [1], [2] format to establish prior work
LENGTH: 2-4 paragraphs
DO NOT: Include detailed methodology or results here. DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "literature"  # Primarily use literature
    },
    
    "literature_review": {
        "name": "Related Work / Literature Review",
        "template": """You are writing the LITERATURE REVIEW section.

CONTEXT FROM LITERATURE:
{literature_context}

USER REQUEST: {query}

INSTRUCTIONS:
1. Organize by themes or techniques (not chronologically)
2. Critically analyze each approach - strengths and limitations
3. Highlight research gaps that YOUR work addresses
4. Compare/contrast different methodologies

TONE: Critical but fair, analytical
CITATIONS: Extensive [1], [2], [3] with comparisons
LENGTH: 3-6 paragraphs depending on field breadth
DO NOT: Describe YOUR methodology here (save for Methods). DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "literature"
    },
    
    "methodology": {
        "name": "Methodology / Methods",
        "template": """You are writing the METHODOLOGY section, describing the STUDENT'S experimental approach.

STUDENT'S RESEARCH METHODS:
{research_context}

RELEVANT PRIOR METHODOLOGIES:
{literature_context}

USER REQUEST: {query}

INSTRUCTIONS:
1. Clearly describe the STUDENT'S experimental setup and procedures
2. Justify design choices with citations to similar approaches [1]
3. Include enough detail for reproducibility
4. Note any novel modifications or adaptations

TONE: Technical, precise, objective
CITATIONS: Moderate - cite to justify methodology choices
LENGTH: 2-4 paragraphs (can be longer for complex setups)
FOCUS: Make it clear this is describing what THE STUDENT did
CRITICAL: DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "research"  # 70% student's methods, 30% literature
    },
    
    "results": {
        "name": "Results",
        "template": """You are writing the RESULTS section, presenting the STUDENT'S experimental findings.

STUDENT'S EXPERIMENTAL DATA:
{research_context}

COMPARISON STUDIES (for context):
{literature_context}

USER REQUEST: {query}

INSTRUCTIONS:
1. Present the STUDENT'S findings objectively
2. Describe patterns, trends, and key observations
3. Reference figures/tables (e.g., "as shown in Figure 1...")
4. Compare with prior work ONLY where directly relevant
5. Save interpretation for Discussion section

TONE: Objective, data-driven, factual
CITATIONS: Minimal - only when comparing to specific prior results
LENGTH: 2-5 paragraphs
DO NOT: Interpret or explain WHY results occurred (that's Discussion). DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "research"  # 80% student's data, 20% comparisons
    },
    
    "discussion": {
        "name": "Discussion",
        "template": """You are writing the DISCUSSION section, interpreting the STUDENT'S results.

STUDENT'S RESULTS AND DATA:
{research_context}

THEORETICAL CONTEXT FROM LITERATURE:
{literature_context}

USER REQUEST: {query}

INSTRUCTIONS:
1. Interpret the STUDENT'S results in light of prior theory
2. Explain WHY the results make sense (or don't)
3. Compare to prior work - consistencies and discrepancies
4. Discuss limitations of the STUDENT'S approach
5. Propose implications and future directions

TONE: Analytical, explanatory, honest about limitations
CITATIONS: Balanced - support interpretations with [1], [2]
LENGTH: 3-5 paragraphs
BALANCE: 50% student's work, 50% literature context
CRITICAL: DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "balanced"
    },
    
    "conclusion": {
        "name": "Conclusion",
        "template": """You are writing the CONCLUSION section.

STUDENT'S CONTRIBUTION SUMMARY:
{research_context}

RESEARCH LANDSCAPE:
{literature_context}

USER REQUEST: {query}

INSTRUCTIONS:
1. Summarize the STUDENT'S main findings and contributions
2. Restate how this addresses the research gap from Introduction
3. Highlight broader implications
4. Suggest 1-2 concrete future research directions

TONE: Confident, forward-looking, concise
CITATIONS: Minimal or none
LENGTH: 1-2 paragraphs
DO NOT: Introduce new results or claims here. DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "research"
    },
    
    # Default for general queries
    "general": {
        "name": "General Academic Writing",
        "template": """You are an academic co-author helping draft scholarly text.

CONTEXT FROM LITERATURE:
{literature_context}

STUDENT'S RESEARCH:
{research_context}

USER REQUEST: {query}

INSTRUCTIONS:
Respond to the user's request in an academic tone.
Use citations [1], [2] where appropriate.
Maintain scholarly precision and objectivity.
CRITICAL: DO NOT output a Reference list or Bibliography at the end of your response. Use ONLY inline citations (e.g., [1], [2]). The full bibliography will be generated later.
""",
        "context_emphasis": "balanced"
    }
}


def get_section_prompt(section_type: str) -> dict:
    """Get prompt configuration for a specific section type"""
    if not section_type:
        section_type = "general"
    section_type = section_type.lower().replace(" ", "_")
    return SECTION_PROMPTS.get(section_type, SECTION_PROMPTS["general"])


def format_section_prompt(
    section_type: str,
    query: str,
    literature_context: str = "",
    research_context: str = "",
    allow_citations: bool = True,
) -> str:
    """Format a section-specific prompt with context"""
    prompt_config = get_section_prompt(section_type)

    prompt = prompt_config["template"].format(
        query=query,
        literature_context=literature_context or "No literature context provided.",
        research_context=research_context or "No research data provided."
    )

    if not allow_citations:
        prompt += "\n\nCRITICAL CITATION RULE:\nNo literature sources were provided. Do NOT invent or include inline citations like [1] or [2]. Write without citations unless grounded sources are later added."

    return prompt


def get_context_weights(section_type: str) -> tuple[float, float]:
    """Get relative weights for literature vs research context
    
    Returns:
        (research_weight, literature_weight) - both between 0 and 1
    """
    prompt_config = get_section_prompt(section_type)
    emphasis = prompt_config.get("context_emphasis", "balanced")
    
    if emphasis == "literature":
        return (0.2, 0.8)  # 20% research, 80% literature
    elif emphasis == "research":
        return (0.8, 0.2)  # 80% research, 20% literature
    else:  # balanced
        return (0.5, 0.5)
