"""Multi-source paper search with concurrent execution"""

from typing import List, Dict
import concurrent.futures
import logging

from app.services.arxiv_client import arxiv_client
# from app.services.semantic_scholar_client import semantic_scholar_client (Removed)
from app.core.config import settings

logger = logging.getLogger(__name__)


def search_arxiv_wrapper(query: str, max_results: int) -> List[Dict]:
    """Wrapper for ArXiv search with error handling"""
    logger.info(f"ArXiv wrapper called with query='{query}', max_results={max_results}")
    try:
        results = arxiv_client.search(query, max_results=max_results)
        logger.info(f"ArXiv client returned {len(results)} raw results")
        # Normalize fields to match expected format
        for paper in results:
            paper['source'] = 'arxiv'
            paper['summary'] = paper.get('abstract', '')
            paper['url'] = paper.get('pdf_url', '')
        logger.info(f"ArXiv wrapper returning {len(results)} formatted papers")
        return results
    except Exception as e:
        logger.error(f"ArXiv search failed for query '{query}': {e}", exc_info=True)
        return []


def search_scholarly_wrapper(query: str, max_results: int) -> List[Dict]:
    """Wrapper for Google Scholar search using scholarly"""
    try:
        from scholarly import scholarly
        
        search_query = scholarly.search_pubs(query)
        results = []
        
        for _ in range(max_results):
            try:
                item = next(search_query)
                bib = item.get('bib', {})
                
                # Robust Author Parsing
                authors = bib.get('author', [])
                if isinstance(authors, str):
                    # Handle "Author A and Author B" or "Author A, Author B"
                    if ' and ' in authors:
                        authors = authors.split(' and ')
                    elif ', ' in authors:
                        authors = authors.split(', ')
                    else:
                        authors = [authors]
                
                # Extract URL securely
                pub_url = item.get('pub_url', '')
                if not pub_url and 'eprint_url' in item:
                    pub_url = item['eprint_url']
                
                # Scholarly sometimes gives direct PDF link in eprint
                pdf_url = item.get('eprint_url', '')
                if not pdf_url and pub_url.endswith('.pdf'):
                    pdf_url = pub_url

                paper = {
                    'title': bib.get('title', 'Unknown Title'),
                    'authors': authors, # Now guaranteed list
                    'year': bib.get('pub_year'),
                    'abstract': bib.get('abstract', 'No abstract available.'),
                    'url': pub_url,
                    'pdf_url': pdf_url, 
                    'source': 'arxiv',
                    'arxiv_id': None,  
                    'citation_count': item.get('num_citations', 0)
                }
                results.append(paper)
            except StopIteration:
                break
                
        return results
    except Exception as e:
        logger.error(f"Google Scholar search failed: {e}")
        return []


def search_all_sources(
    query: str,
    max_results_per_source: int = 5
) -> List[Dict]:
    """
    Search papers from multiple sources concurrently
    
    Args:
        query: Search query
        max_results_per_source: Maximum results from each source
    
    Returns:
        Deduplicated list of papers from all sources
    """
    logger.info(f"===  SEARCH_ALL_SOURCES START: query='{query}', max_results={max_results_per_source} ===")
    
    # Check if we should use mock mode (for development)
    if getattr(settings, 'mock_ai_responses', False):
        logger.info(f"MOCK MODE ACTIVE: Returning mock papers for query '{query}'")
        return _get_mock_papers()
    
    logger.info(f"REAL MODE: Searching ArXiv only...")
    
    # SIMPLIFIED: Use ArXiv only (fast, reliable, no auth needed)
    all_papers = []
    
    try:
        logger.info("Calling ArXiv API...")
        arxiv_papers = search_arxiv_wrapper(query, max_results_per_source * 2)  # Get more from ArXiv
        logger.info(f"ArXiv returned {len(arxiv_papers)} papers")
        
        all_papers = arxiv_papers
        logger.info(f"Total papers BEFORE deduplication: {len(all_papers)}")
        
    except Exception as e:
        logger.error(f"Error in ArXiv search: {e}", exc_info=True)
        # FIXED: Don't return mock papers in production - return empty with proper error
        logger.error("ArXiv search failed. Returning empty results.")
        return []  # Empty list allows proper error handling upstream
    
    # Deduplicate by title (case-insensitive)
    seen_titles = set()
    deduplicated = []
    
    for paper in all_papers:
        title = paper.get('title', '').lower().strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            deduplicated.append(paper)
    
    logger.info(f"After deduplication: {len(deduplicated)} unique papers")
    
    # Return top results
    return deduplicated[:max_results_per_source * 2]


def _get_mock_papers() -> List[Dict]:
    """Return mock papers for testing/development"""
    return [
        {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "summary": "We explore retrieval-augmented generation (RAG) models which retrieve documents from a knowledge store to help generate answers.",
            "abstract": "We explore retrieval-augmented generation (RAG) models which retrieve documents from a knowledge store to help generate answers.",
            "authors": ["Patrick Lewis", "Ethan Perez", "Aleksandra Piktus"],
            "pdf_url": "https://arxiv.org/pdf/2005.11401.pdf",
            "url": "https://arxiv.org/pdf/2005.11401.pdf",
            "source": "arxiv",
            "year": 2020,
            "venue": "NeurIPS",
            "arxiv_id": "2005.11401",
            "citation_count": 1500
        },
        {
            "title": "Attention Is All You Need",
            "summary": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
            "abstract": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
            "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
            "url": "https://arxiv.org/pdf/1706.03762.pdf",
            "source": "arxiv",
            "year": 2017,
            "venue": "NeurIPS",
            "arxiv_id": "1706.03762",
            "citation_count": 50000
        }
    ]
