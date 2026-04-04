"""Service for downloading PDFs from arXiv"""

from pathlib import Path
from typing import Optional
import logging
import httpx

logger = logging.getLogger(__name__)


async def download_arxiv_pdf(
    arxiv_id: str,
    download_dir: Path,
    timeout: int = 30
) -> Optional[Path]:
    """
    Download PDF from arXiv
    
    Args:
        arxiv_id: arXiv ID (e.g., "1706.03762")
        download_dir: Directory to save PDF
        timeout: Download timeout in seconds
    
    Returns:
        Path to downloaded PDF or None if failed
    """
    try:
        # Clean arxiv_id (remove version if present)
        clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
        
        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        
        # Create download directory
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        filename = f"{clean_id.replace('/', '_').replace('.', '_')}.pdf"
        filepath = download_dir / filename
        
        # Download PDF
        async with httpx.AsyncClient() as client:
            response = await client.get(pdf_url, timeout=timeout, follow_redirects=True)
            response.raise_for_status()
            
            # Save to file
            with open(filepath, 'wb') as f:
                f.write(response.content)
        
        logger.info(f"Downloaded PDF: {arxiv_id} -> {filepath}")
        return filepath
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading {arxiv_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error downloading PDF for {arxiv_id}: {e}")
        return None


def get_pdf_url(arxiv_id: str) -> str:
    """Get PDF URL for an arXiv paper"""
    clean_id = arxiv_id.split('v')[0] if 'v' in arxiv_id else arxiv_id
    return f"https://arxiv.org/pdf/{clean_id}.pdf"
