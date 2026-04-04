"""Semantic Scholar API client for paper search"""

import requests
from typing import List, Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)


class SemanticScholarClient:
    """Client for searching papers using Semantic Scholar API"""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Semantic Scholar client
        
        Args:
            api_key: Optional API key for higher rate limits
                    Get one at: https://www.semanticscholar.org/product/api
        """
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests (10 req/sec max without API key)
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_request)
        
        self.last_request_time = time.time()
    
    def search(
        self,
        query: str,
        limit: int = 10,
        fields: Optional[List[str]] = None,
        year: Optional[str] = None,
        publication_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search for papers
        
        Args:
            query: Search query
            limit: Maximum number of results (max 100)
            fields: Fields to return (default: title, abstract, authors, year, citationCount)
            year: Year filter (e.g., "2020", "2015-2020")
            publication_types: Filter by publication type (e.g., ["JournalArticle", "Conference"])
        
        Returns:
            List of paper dictionaries
        """
        self._rate_limit()
        
        if fields is None:
            fields = [
                "paperId", "title", "abstract", "authors", "year",
                "citationCount", "referenceCount", "fieldsOfStudy",
                "publicationTypes", "publicationDate", "journal",
                "externalIds"
            ]
        
        try:
            url = f"{self.BASE_URL}/paper/search"
            params = {
                "query": query,
                "limit": min(limit, 100),
                "fields": ",".join(fields)
            }
            
            if year:
                params["year"] = year
            if publication_types:
                params["publicationTypes"] = ",".join(publication_types)
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            papers = data.get("data", [])
            
            # Transform to consistent format
            results = []
            for paper in papers:
                results.append({
                    'paper_id': paper.get('paperId'),
                    'title': paper.get('title'),
                    'abstract': paper.get('abstract'),
                    'authors': [author.get('name') for author in paper.get('authors', [])],
                    'year': paper.get('year'),
                    'publication_date': paper.get('publicationDate'),
                    'citation_count': paper.get('citationCount', 0),
                    'reference_count': paper.get('referenceCount', 0),
                    'fields_of_study': paper.get('fieldsOfStudy', []),
                    'publication_types': paper.get('publicationTypes', []),
                    'journal': paper.get('journal', {}).get('name') if paper.get('journal') else None,
                    'doi': paper.get('externalIds', {}).get('DOI'),
                    'arxiv_id': paper.get('externalIds', {}).get('ArXiv'),
                    'url': f"https://www.semanticscholar.org/paper/{paper.get('paperId')}"
                })
            
            logger.info(f"Found {len(results)} papers on Semantic Scholar for: {query}")
            return results
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Semantic Scholar: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []
    
    def get_paper_by_id(self, paper_id: str, fields: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Get paper by Semantic Scholar ID
        
        Args:
            paper_id: Semantic Scholar paper ID
            fields: Fields to return
        
        Returns:
            Paper dictionary or None
        """
        self._rate_limit()
        
        if fields is None:
            fields = ["paperId", "title", "abstract", "authors", "year", "citationCount"]
        
        try:
            url = f"{self.BASE_URL}/paper/{paper_id}"
            params = {"fields": ",".join(fields)}
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error fetching paper {paper_id}: {e}")
            return None
    
    def get_recommendations(self, paper_id: str, limit: int = 10) -> List[Dict]:
        """Get paper recommendations based on a paper"""
        self._rate_limit()
        
        try:
            url = f"{self.BASE_URL}/paper/{paper_id}/recommendations"
            params = {
                "fields": "paperId,title,abstract,authors,year,citationCount",
                "limit": limit
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            return data.get("recommendedPapers", [])
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []


# Singleton instance
semantic_scholar_client = SemanticScholarClient()
