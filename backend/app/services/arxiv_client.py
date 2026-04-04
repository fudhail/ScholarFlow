
import arxiv
from typing import List, Dict, Optional
import logging
from pathlib import Path
import time
import asyncio

logger = logging.getLogger(__name__)


class ArxivClient:
    """Client for searching and fetching papers from arXiv with rate limiting"""
    
    def __init__(self):
        self.client = arxiv.Client()
        self.last_request_time = 0
        self.min_delay = 3.0  # ArXiv recommends 3 seconds between requests
    
    def _wait_for_rate_limit(self):
        """Ensure minimum delay between requests to respect ArXiv rate limits"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            sleep_time = self.min_delay - elapsed
            logger.info(f"⏱️  Rate limiting: waiting {sleep_time:.1f}s before next request")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def search(
        self,
        query: str,
        max_results: int = 10,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance
    ) -> List[Dict]:
        """
        Search arXiv for papers matching the query
        
        Args:
            query: Search query (can use arXiv query syntax)
            max_results: Maximum number of results to return
            sort_by: Sort criterion (Relevance, LastUpdatedDate, SubmittedDate)
        
        Returns:
            List of paper dictionaries with metadata
        """
        """
        Search arXiv for papers matching the query
        
        Args:
            query: Search query (can use arXiv query syntax)
            max_results: Maximum number of results to return
            sort_by: Sort criterion (Relevance, LastUpdatedDate, SubmittedDate)
        
        Returns:
            List of paper dictionaries with metadata
        """
        logger.info(f"=== ArXiv Client Search START ===")
        logger.info(f"Query: '{query}', Max Results: {max_results}")
        
        import urllib.request
        import urllib.parse
        import xml.etree.ElementTree as ET
        
        try:
            # Construct API URL
            base_url = 'http://export.arxiv.org/api/query?'
            
            # Map sort criteria if possible, or default to relevance
            sort_param = 'relevance'
            if sort_by == arxiv.SortCriterion.LastUpdatedDate:
                sort_param = 'lastUpdatedDate'
            elif sort_by == arxiv.SortCriterion.SubmittedDate:
                sort_param = 'submittedDate'
                
            params = {
                'search_query': query,
                'start': 0,
                'max_results': max_results,
                'sortBy': sort_param,
                'sortOrder': 'descending'
            }
            
            query_string = urllib.parse.urlencode(params)
            url = base_url + query_string
            
            logger.info(f"Calling ArXiv API: {url}")
            
            # Respect rate limits before making request
            self._wait_for_rate_limit()
            
            # Retry logic with exponential backoff for rate limiting (429 errors)
            max_retries = 3
            retry_count = 0
            data = None
            
            while retry_count < max_retries:
                try:
                    with urllib.request.urlopen(url, timeout=15) as response:
                        data = response.read()
                        break  # Success, exit retry loop
                        
                except urllib.error.HTTPError as http_err:
                    if http_err.code == 429:  # Rate limit error
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count  # Exponential backoff: 2s, 4s, 8s
                            logger.warning(f"⚠️  ArXiv rate limit hit (429). Retry {retry_count}/{max_retries} after {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"❌ ArXiv rate limit exceeded after {max_retries} retries")
                            return []
                    else:
                        logger.error(f"HTTP Error {http_err.code}: {http_err}")
                        return []
                        
                except urllib.error.URLError as url_err:
                    logger.error(f"URLError accessing ArXiv: {url_err}")
                    logger.error(f"Check network connection or ArXiv availability")
                    return []
                    
                except Exception as req_err:
                    logger.error(f"Request error: {req_err}", exc_info=True)
                    return []
            
            if data is None:
                logger.error("Failed to retrieve data from ArXiv after retries")
                return []
                
            logger.info(f"Received {len(data)} bytes from ArXiv")
            
            # Parse XML
            root = ET.fromstring(data)
            
            # ArXiv API uses Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
            
            # Count entries
            entries = root.findall('atom:entry', ns)
            logger.info(f"Found {len(entries)} entries in XML response")
            
            if len(entries) == 0:
                logger.warning(f"ArXiv returned 0 entries for query: '{query}'")
                logger.warning("This may indicate the query is too specific or uses unsupported syntax")
                return []
            
            results = []
            count = 0
            
            for entry in root.findall('atom:entry', ns):
                count += 1
                try:
                    # Extract fields
                    id_url = entry.find('atom:id', ns).text
                    arxiv_id = id_url.split('/')[-1]
                    
                    title = entry.find('atom:title', ns).text.strip()
                    title = ' '.join(title.split()) # Normalize whitespace
                    
                    summary = entry.find('atom:summary', ns).text.strip()
                    
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name = author.find('atom:name', ns).text
                        authors.append(name)
                        
                    published = entry.find('atom:published', ns).text
                    updated = entry.find('atom:updated', ns).text
                    
                    # Links
                    pdf_url = None
                    doi = None
                    journal_ref = None
                    
                    for link in entry.findall('atom:link', ns):
                        rel = link.get('rel')
                        href = link.get('href')
                        if rel == 'related' and link.get('title') == 'pdf':
                            pdf_url = href
                        elif rel == 'alternate' and link.get('type') == 'text/html':
                             pass # Main page
                             
                    # Optional fields
                    doi_elem = entry.find('arxiv:doi', ns)
                    if doi_elem is not None:
                        doi = doi_elem.text
                        
                    journal_elem = entry.find('arxiv:journal_ref', ns)
                    if journal_elem is not None:
                        journal_ref = journal_elem.text
                        
                    comment_elem = entry.find('arxiv:comment', ns)
                    comment = comment_elem.text if comment_elem is not None else None
                    
                    category = entry.find('arxiv:primary_category', ns)
                    primary_category = category.get('term') if category is not None else None
                    
                    categories = [c.get('term') for c in entry.findall('atom:category', ns)]

                    logger.info(f"Processing paper {count}: {title[:60]}...")
                    
                    results.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'authors': authors,
                        'abstract': summary,
                        'year': int(published[:4]) if published else None,
                        'published_date': published,
                        'updated_date': updated,
                        'pdf_url': pdf_url or id_url.replace('abs', 'pdf'),
                        'primary_category': primary_category,
                        'categories': categories,
                        'doi': doi,
                        'journal_ref': journal_ref,
                        'comment': comment
                    })
                except Exception as parse_err:
                     logger.warning(f"Error parsing paper entry {count}: {parse_err}")
                     continue
            
            logger.info(f"=== ArXiv Client Search COMPLETE: Found {len(results)} papers ===")
            return results
            
        except Exception as e:
            logger.error(f"Error searching arXiv for query '{query}': {e}", exc_info=True)
            return []
    
    def search_by_id(self, arxiv_id: str) -> Optional[Dict]:
        """
        Get a specific paper by its arXiv ID
        
        Args:
            arxiv_id: arXiv ID (e.g., "1706.03762" or "1706.03762v2")
        
        Returns:
            Paper dictionary or None if not found
        """
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(self.client.results(search))
            
            return {
                'arxiv_id': paper.entry_id.split('/')[-1],
                'title': paper.title,
                'authors': [author.name for author in paper.authors],
                'abstract': paper.summary,
                'year': paper.published.year if paper.published else None,
                'published_date': paper.published.isoformat() if paper.published else None,
                'pdf_url': paper.pdf_url,
                'primary_category': paper.primary_category,
                'categories': paper.categories,
                'doi': paper.doi
            }
            
        except StopIteration:
            logger.warning(f"Paper not found: {arxiv_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching paper {arxiv_id}: {e}")
            return None
    
    def download_pdf(
        self,
        arxiv_id: str,
        download_dir: Path,
        filename: Optional[str] = None
    ) -> Optional[Path]:
        """
        Download PDF for a paper
        
        Args:
            arxiv_id: arXiv ID
            download_dir: Directory to save the PDF
            filename: Optional custom filename (defaults to arxiv_id.pdf)
        
        Returns:
            Path to downloaded PDF or None if failed
        """
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            paper = next(self.client.results(search))
            
            download_dir.mkdir(parents=True, exist_ok=True)
            
            if filename is None:
                filename = f"{arxiv_id.replace('/', '_')}.pdf"
            
            filepath = download_dir / filename
            
            paper.download_pdf(dirpath=str(download_dir), filename=filename)
            
            logger.info(f"Downloaded PDF for {arxiv_id} to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error downloading PDF for {arxiv_id}: {e}")
            return None
    
    def search_by_author(self, author_name: str, max_results: int = 10) -> List[Dict]:
        """Search papers by author name"""
        query = f"au:{author_name}"
        return self.search(query, max_results)
    
    def search_by_category(
        self,
        category: str,
        keywords: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict]:
        """
        Search papers in a specific category
        
        Args:
            category: arXiv category (e.g., "cs.AI", "cs.CL", "cs.LG")
            keywords: Optional keywords to filter by
            max_results: Maximum results
        """
        if keywords:
            query = f"cat:{category} AND all:{keywords}"
        else:
            query = f"cat:{category}"
        
        return self.search(query, max_results, sort_by=arxiv.SortCriterion.LastUpdatedDate)


# Singleton instance
arxiv_client = ArxivClient()
