#!/usr/bin/env python3
"""
Collect academic training data for fine-tuning ScholarMate model
IMPROVED: Downloads full papers and extracts sections (Intro, Methods, Results, etc.)
Sources: ArXiv full-text PDFs
"""
import arxiv
import json
from pathlib import Path
from typing import List, Dict, Optional
import logging
import re
import time
import urllib.request

# For PDF parsing
try:
    import PyPDF2
    HAS_PDF_PARSER = True
except ImportError:
    print("⚠️  PyPDF2 not found. Install with: pip install PyPDF2")
    HAS_PDF_PARSER = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/training")
PDF_DIR = Path("data/papers/pdfs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

def fetch_arxiv_papers(categories: List[str], max_results: int = 1000) -> List[Dict]:
    """Fetch papers from ArXiv for training data"""
    papers = []
    
    for category in categories:
        logger.info(f"Fetching {category} papers...")
        search = arxiv.Search(
            query=f"cat:{category}",
            max_results=max_results // len(categories),
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        
        for result in search.results():
            papers.append({
                "title": result.title,
                "abstract": result.summary,
                "authors": [author.name for author in result.authors],
                "categories": result.categories,
                "arxiv_id": result.entry_id.split('/')[-1],
                "pdf_url": result.pdf_url
            })
    
    logger.info(f"Collected {len(papers)} papers")
    return papers

def download_pdf(pdf_url: str, arxiv_id: str) -> Optional[Path]:
    """Download PDF from ArXiv"""
    pdf_path = PDF_DIR / f"{arxiv_id.replace('/', '_')}.pdf"
    
    if pdf_path.exists():
        logger.debug(f"PDF already exists: {pdf_path}")
        return pdf_path
    
    try:
        logger.info(f"Downloading {arxiv_id}...")
        urllib.request.urlretrieve(pdf_url, pdf_path)
        time.sleep(1)  # Be nice to ArXiv servers
        return pdf_path
    except Exception as e:
        logger.error(f"Failed to download {arxiv_id}: {e}")
        return None

def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """Extract text from PDF"""
    if not HAS_PDF_PARSER:
        return None
    
    try:
        with pdf_path.open('rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}")
        return None

def parse_paper_sections(text: str) -> Dict[str, str]:
    """
    Parse paper into sections (Introduction, Methods, Results, etc.)
    Uses common section headers in academic papers
    """
    sections = {}
    
    # Common section patterns (case-insensitive)
    section_patterns = {
        'abstract': r'\n\s*abstract\s*\n',
        'introduction': r'\n\s*(?:1\.?\s+)?introduction\s*\n',
        'related_work': r'\n\s*(?:2\.?\s+)?related\s+work\s*\n',
        'methodology': r'\n\s*(?:\d+\.?\s+)?(?:methodology|methods?|approach)\s*\n',
        'experiments': r'\n\s*(?:\d+\.?\s+)?(?:experiments?|evaluation|results?)\s*\n',
        'discussion': r'\n\s*(?:\d+\.?\s+)?discussion\s*\n',
        'conclusion': r'\n\s*(?:\d+\.?\s+)?conclusions?\s*\n',
    }
    
    text_lower = text.lower()
    
    # Find all section positions
    section_positions = []
    for section_name, pattern in section_patterns.items():
        matches = list(re.finditer(pattern, text_lower, re.IGNORECASE))
        for match in matches:
            section_positions.append((match.start(), section_name))
    
    # Sort by position
    section_positions.sort()
    
    # Extract text between sections
    for i, (start_pos, section_name) in enumerate(section_positions):
        if i + 1 < len(section_positions):
            end_pos = section_positions[i + 1][0]
        else:
            end_pos = len(text)
        
        # Extract section text (skip the header line)
        section_text = text[start_pos:end_pos].strip()
        # Remove the header itself
        section_text = re.sub(r'^.*?\n', '', section_text, count=1)
        
        if len(section_text) > 100:  # Only keep substantial sections
            sections[section_name] = section_text[:3000]  # Limit length
    
    return sections

def identify_paper_type(title: str, abstract: str, sections: Dict[str, str]) -> str:
    """Identify the type of research paper based on content"""
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    
    # Survey/Review papers
    if any(word in title_lower for word in ['survey', 'review', 'overview', 'taxonomy']):
        return "survey"
    
    # Theoretical papers
    if any(word in abstract_lower for word in ['theorem', 'proof', 'lemma', 'formally prove', 'theoretical analysis']):
        return "theoretical"
    
    # Application papers
    if any(word in abstract_lower for word in ['application', 'system', 'tool', 'framework', 'implementation']):
        return "application"
    
    # Has experiments section = experimental paper
    if 'experiments' in sections or 'evaluation' in sections:
        return "experimental"
    
    return "experimental"  # Default

def get_expected_sections_for_type(paper_type: str) -> List[str]:
    """Return expected sections based on paper type"""
    section_templates = {
        "experimental": [
            "Abstract",
            "Introduction", 
            "Related Work",
            "Methodology",
            "Experiments",
            "Results",
            "Discussion",
            "Conclusion",
            "References"
        ],
        "theoretical": [
            "Abstract",
            "Introduction",
            "Preliminaries",
            "Main Results",
            "Proofs",
            "Discussion",
            "Conclusion",
            "References"
        ],
        "survey": [
            "Abstract",
            "Introduction",
            "Background",
            "Survey of Approaches",
            "Comparative Analysis",
            "Discussion",
            "Conclusion",
            "References"
        ],
        "application": [
            "Abstract",
            "Introduction",
            "Related Work",
            "System Design",
            "Implementation",
            "Evaluation",
            "Discussion",
            "Conclusion",
            "References"
        ]
    }
    return section_templates.get(paper_type, section_templates["experimental"])

def create_instruction_pairs(papers: List[Dict]) -> List[Dict]:
    """
    Convert papers into section-specific instruction-following format
    Teaches model how to write each paper section properly + plan based on paper type
    """
    training_data = []
    
    for paper in papers:
        title = paper['title']
        abstract = paper['abstract']
        sections = paper.get('sections', {})
        
        # Identify paper type
        paper_type = identify_paper_type(title, abstract, sections)
        expected_sections = get_expected_sections_for_type(paper_type)
        
        # Task 1: Write Introduction Section
        if 'introduction' in sections:
            intro_text = sections['introduction']
            training_data.append({
                "instruction": f"Write an introduction section for a research paper on the following topic:\n\nTitle: {title}\n\nAbstract: {abstract[:300]}...\n\nWrite a comprehensive introduction that motivates the research, reviews related work, and states the main contributions.",
                "output": intro_text
            })
        
        # Task 2: Write Methodology Section
        if 'methodology' in sections:
            method_text = sections['methodology']
            training_data.append({
                "instruction": f"Write a methodology section for the following research:\n\nTitle: {title}\n\nResearch Goal: {abstract[:200]}...\n\nDescribe the methods, approach, and experimental setup in detail.",
                "output": method_text
            })
        
        # Task 3: Write Results Section
        if 'experiments' in sections:
            results_text = sections['experiments']
            training_data.append({
                "instruction": f"Write a results section that presents experimental findings for:\n\nTitle: {title}\n\nMethodology context: {sections.get('methodology', abstract)[:200]}...\n\nPresent results clearly with proper analysis.",
                "output": results_text
            })
        
        # Task 4: Write Conclusion Section
        if 'conclusion' in sections:
            conclusion_text = sections['conclusion']
            training_data.append({
                "instruction": f"Write a conclusion section that summarizes the research:\n\nTitle: {title}\n\nAbstract: {abstract[:200]}...\n\nSummarize findings, implications, and future work.",
                "output": conclusion_text
            })
        
        # Task 5: Identify Paper Type and Required Sections
        actual_sections = list(sections.keys()) if sections else []
        training_data.append({
            "instruction": f"Analyze the following research paper and determine what type it is and what sections it should include:\n\nTitle: {title}\n\nAbstract: {abstract}\n\nProvide the paper type and recommended section structure.",
            "output": f"Paper Type: {paper_type.capitalize()}\n\nThis is a {paper_type} paper. Based on the research objectives and methodology, the paper should include the following sections:\n\n" + 
                     "\n".join([f"{i+1}. {section}" for i, section in enumerate(expected_sections)]) +
                     f"\n\nRationale: {paper_type.capitalize()} papers require this structure because they " +
                     ("present experimental results and need sections for methodology, experiments, and analysis." if paper_type == "experimental" 
                      else "develop theoretical contributions and need rigorous proofs and formal analysis." if paper_type == "theoretical"
                      else "synthesize existing research and need comprehensive literature coverage." if paper_type == "survey"
                      else "describe system implementation and need design and evaluation sections.")
        })
        
        # Task 6: Generate Detailed Research Plan Based on Paper Type
        if 'introduction' in sections and 'methodology' in sections:
            plan_sections = "\n".join([f"   - {section}" for section in expected_sections[1:-1]])  # Skip Abstract and References
            training_data.append({
                "instruction": f"Create a detailed research plan for writing a {paper_type} paper on:\n\nTitle: {title}\n\nObjective: {abstract[:200]}...\n\nInclude the paper structure, key sections, and what each section should cover.",
                "output": f"Research Paper Plan ({paper_type.capitalize()} Paper)\n\n"
                         f"Paper Type: {paper_type.capitalize()}\n\n"
                         f"Proposed Structure:\n{plan_sections}\n\n"
                         f"Section Details:\n\n"
                         f"1. Introduction:\n{sections['introduction'][:250]}...\n\n"
                         f"2. Methodology:\n{sections['methodology'][:250]}...\n\n" +
                         (f"3. Results:\n{sections.get('experiments', 'Present experimental findings, performance metrics, and comparative analysis with baselines.')[:250]}...\n\n" if paper_type == "experimental" else "") +
                         f"Expected Contributions:\nThis {paper_type} paper will advance the field by providing " +
                         ("empirical evidence and experimental validation." if paper_type == "experimental"
                          else "theoretical insights and formal proofs." if paper_type == "theoretical"
                          else "a comprehensive overview and comparative analysis." if paper_type == "survey"
                          else "a practical implementation and evaluation.")
            })
        
        # Task 7: Paper Summarization (keep this for general understanding)
        training_data.append({
            "instruction": f"Provide a comprehensive summary of this research paper:\n\nTitle: {title}\n\nAbstract: {abstract}",
            "output": f"This {paper_type} paper presents {title}. {abstract[:400]}... The research makes significant contributions to the field through its {'experimental validation and empirical results' if paper_type == 'experimental' else 'theoretical analysis and formal proofs' if paper_type == 'theoretical' else 'comprehensive literature review' if paper_type == 'survey' else 'practical system implementation'}."
        })
        
        # Task 8: Section Structure Analysis
        if len(sections) > 2:
            actual_section_list = ", ".join(actual_sections)
            training_data.append({
                "instruction": f"Analyze the structure of this {paper_type} paper:\n\nTitle: {title}\n\nAbstract: {abstract[:200]}...\n\nWhat sections does it have and why is this structure appropriate?",
                "output": f"This {paper_type} paper includes the following sections: {actual_section_list}.\n\n"
                         f"Structure Analysis:\n"
                         f"- The paper follows standard {paper_type} paper conventions\n"
                         f"- Introduction: Motivates the research problem and states contributions\n" +
                         ("- Methodology: Describes the experimental approach and implementation details\n"
                          "- Experiments: Presents experimental setup, datasets, and evaluation metrics\n"
                          "- Results: Reports findings with quantitative analysis\n" if paper_type == "experimental" 
                          else "- Preliminaries: Establishes formal definitions and notation\n"
                               "- Main Results: Presents theorems and propositions\n"
                               "- Proofs: Provides rigorous mathematical proofs\n" if paper_type == "theoretical"
                          else "- Survey: Comprehensively reviews existing approaches\n"
                               "- Comparative Analysis: Evaluates strengths and weaknesses of methods\n" if paper_type == "survey"
                          else "- System Design: Describes architecture and components\n"
                               "- Implementation: Details technical implementation\n"
                               "- Evaluation: Assesses system performance\n") +
                         f"- Conclusion: Summarizes contributions and suggests future work\n\n"
                         f"This structure is appropriate because {paper_type} papers need to " +
                         ("demonstrate empirical validation through rigorous experiments." if paper_type == "experimental"
                          else "provide formal mathematical foundations and proofs." if paper_type == "theoretical"
                          else "synthesize and compare existing research comprehensively." if paper_type == "survey"
                          else "showcase practical implementation and real-world evaluation.")
            })
        
        # Task 9: Related Work Writing
        if 'related_work' in sections:
            related_text = sections['related_work']
            training_data.append({
                "instruction": f"Write a related work section that reviews prior research for:\n\nTitle: {title}\n\nTopic: {abstract[:200]}...\n\nSurvey relevant literature and position this work.",
                "output": related_text
            })
        
        # Task 10: Paper Type-Specific Planning Question
        training_data.append({
            "instruction": f"I want to write a research paper about: {title[:100]}. What type of paper should this be and what sections do I need?",
            "output": f"Based on your topic, this should be a {paper_type} paper.\n\n"
                     f"Recommended Paper Structure:\n\n" +
                     "\n".join([f"{i+1}. **{section}**" + 
                               (f" - Introduce the problem, motivation, and contributions" if section == "Introduction"
                                else f" - Review existing methods and related research" if section == "Related Work"
                                else f" - Describe your approach, algorithms, and methodology" if section == "Methodology"
                                else f" - Detail experimental setup, datasets, and protocols" if section == "Experiments"
                                else f" - Present findings, metrics, and analysis" if section == "Results"
                                else f" - Interpret results and compare with baselines" if section == "Discussion"
                                else f" - Summarize contributions and future directions" if section == "Conclusion"
                                else f" - Define notation and formal preliminaries" if section == "Preliminaries"
                                else f" - State theorems and main results" if section == "Main Results"
                                else f" - Provide mathematical proofs" if section == "Proofs"
                                else f" - Comprehensively survey existing approaches" if section == "Survey of Approaches"
                                else f" - Compare and evaluate different methods" if section == "Comparative Analysis"
                                else f" - Describe system architecture" if section == "System Design"
                                else f" - Detail technical implementation" if section == "Implementation"
                                else f" - Assess system performance and usability" if section == "Evaluation"
                                else "")
                               for i, section in enumerate(expected_sections)]) +
                     f"\n\nWhy this structure: {paper_type.capitalize()} papers require " +
                     ("experimental validation, so you need sections to describe your methodology, experiments, and results." if paper_type == "experimental"
                      else "formal analysis, so you need sections for preliminaries, theorems, and proofs." if paper_type == "theoretical"
                      else "comprehensive literature coverage, so you need sections to survey and compare existing work." if paper_type == "survey"
                      else "practical demonstration, so you need sections for system design, implementation, and evaluation.")
        })
    
    return training_data

def save_training_data(data: List[Dict], filename: str):
    """Save in JSONL format for Ollama fine-tuning"""
    output_path = OUTPUT_DIR / filename
    
    with output_path.open('w', encoding='utf-8') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')
    
    logger.info(f"Saved {len(data)} training examples to {output_path}")

if __name__ == "__main__":
    # Focus on CS/ML/AI categories
    categories = [
        "cs.AI",  # Artificial Intelligence
        "cs.CL",  # Computation and Language
        "cs.LG",  # Machine Learning
        "cs.CV",  # Computer Vision
    ]
    
    logger.info("🚀 Starting training data collection...")
    logger.info("This will download full papers and extract sections")
    
    # Step 1: Fetch paper metadata
    logger.info("Step 1: Fetching paper metadata from ArXiv...")
    papers = fetch_arxiv_papers(categories, max_results=1000)
    
    # Step 2: Download PDFs and extract sections
    logger.info("Step 2: Downloading PDFs and extracting sections...")
    papers_with_sections = []
    
    for i, paper in enumerate(papers):
        logger.info(f"Processing {i+1}/{len(papers)}: {paper['arxiv_id']}")
        
        # Download PDF
        pdf_path = download_pdf(paper['pdf_url'], paper['arxiv_id'])
        if not pdf_path:
            continue
        
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"Could not extract text from {paper['arxiv_id']}")
            continue
        
        # Parse sections
        sections = parse_paper_sections(text)
        if sections:
            paper['sections'] = sections
            papers_with_sections.append(paper)
            logger.info(f"  ✓ Extracted {len(sections)} sections: {list(sections.keys())}")
        
        # Limit to avoid excessive processing
        if len(papers_with_sections) >= 200:
            logger.info(f"Reached target of 200 papers with sections")
            break
    
    logger.info(f"Successfully processed {len(papers_with_sections)} papers")
    
    # Step 3: Create section-specific training examples
    logger.info("Step 3: Creating section-specific training examples...")
    training_data = create_instruction_pairs(papers_with_sections)
    
    # Step 4: Save training data
    logger.info("Step 4: Saving training data...")
    save_training_data(training_data, "scholarmate_training.jsonl")
    
    logger.info("✅ Training data collection complete!")
    logger.info(f"Total papers processed: {len(papers_with_sections)}")
    logger.info(f"Total training examples: {len(training_data)}")
    logger.info(f"Training file: {OUTPUT_DIR / 'scholarmate_training.jsonl'}")
    
    # Print statistics
    section_counts = {}
    paper_type_counts = {"experimental": 0, "theoretical": 0, "survey": 0, "application": 0}
    
    for paper in papers_with_sections:
        # Count sections
        for section in paper.get('sections', {}).keys():
            section_counts[section] = section_counts.get(section, 0) + 1
        
        # Count paper types
        paper_type = identify_paper_type(paper['title'], paper['abstract'], paper.get('sections', {}))
        paper_type_counts[paper_type] = paper_type_counts.get(paper_type, 0) + 1
    
    logger.info("\n📊 Paper Type Distribution:")
    for paper_type, count in sorted(paper_type_counts.items(), key=lambda x: -x[1]):
        percentage = (count / len(papers_with_sections)) * 100
        logger.info(f"  {paper_type.capitalize()}: {count} papers ({percentage:.1f}%)")
    
    logger.info("\n📄 Section Statistics:")
    for section, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {section}: {count} papers")
    
    logger.info("\n✅ Model will learn:")
    logger.info(f"  - How to write {len(section_counts)} different section types")
    logger.info(f"  - Structure for {len(paper_type_counts)} paper types")
    logger.info(f"  - Planning based on paper type and research goals")
    logger.info(f"  - Section analysis and recommendations")
