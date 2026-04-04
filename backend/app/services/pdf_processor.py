"""PDF processing service for chunking papers"""

from pathlib import Path
from typing import List, Dict
import logging

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF file
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.warning("pdfplumber not available, skipping PDF extraction")
        return ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            full_text = "\n\n".join(text_parts)
            logger.info(f"Extracted {len(full_text)} characters from {pdf_path.name}")
            return full_text
            
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[str]:
    """
    Split text into overlapping chunks
    
    Args:
        text: Text to chunk
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at sentence boundary
        if end < len(text):
            # Look for period within last 100 chars
            last_period = text[max(start, end - 100):end].rfind('. ')
            if last_period != -1:
                end = max(start, end - 100) + last_period + 2
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - chunk_overlap
    
    logger.info(f"Created {len(chunks)} chunks from {len(text)} characters")
    return chunks


def chunk_pdf(
    pdf_path: Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Dict[str, any]]:
    """
    Extract and chunk PDF into segments with metadata
    
    Args:
        pdf_path: Path to PDF file
        chunk_size: Maximum chunk size
        chunk_overlap: Overlap between chunks
    
    Returns:
        List of chunk dictionaries with text and metadata
    """
    # Extract full text
    text = extract_text_from_pdf(pdf_path)
    
    if not text:
        return []
    
    # Split into chunks
    chunks = chunk_text(text, chunk_size, chunk_overlap)
    
    # Add metadata
    chunks_with_metadata = []
    for i, chunk_text in enumerate(chunks):
        chunks_with_metadata.append({
            "text": chunk_text,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "source_file": pdf_path.name
        })
    
    return chunks_with_metadata


def chunk_pdf_with_pages(
    pdf_path: Path,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> List[Dict[str, any]]:
    """
    Extract and chunk PDF into segments WITH PAGE NUMBER TRACKING.
    
    This is the enhanced version that enables "click to open PDF at page" 
    functionality for ScholarMate citations.
    
    Args:
        pdf_path: Path to PDF file
        chunk_size: Maximum chunk size
        chunk_overlap: Overlap between chunks
    
    Returns:
        List of chunk dictionaries with text, metadata, AND page_number
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.warning("pdfplumber not available, skipping PDF extraction")
        return []
    
    chunks_with_metadata = []
    chunk_index = 0
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                
                if not page_text:
                    continue
                
                # Chunk this page's text
                page_chunks = chunk_text(page_text, chunk_size, chunk_overlap)
                
                for chunk in page_chunks:
                    chunks_with_metadata.append({
                        "text": chunk,
                        "chunk_index": chunk_index,
                        "page_number": page_num,  # ← KEY: Track page number!
                        "source_file": pdf_path.name,
                        "pdf_path": str(pdf_path)
                    })
                    chunk_index += 1
        
        # Update total_chunks
        for chunk in chunks_with_metadata:
            chunk["total_chunks"] = len(chunks_with_metadata)
        
        logger.info(f"Created {len(chunks_with_metadata)} page-tracked chunks from {pdf_path.name}")
        return chunks_with_metadata
        
    except Exception as e:
        logger.error(f"Error chunking PDF with pages {pdf_path}: {e}")
        return []


def extract_text_by_page(pdf_path: Path) -> List[Dict[str, any]]:
    """
    Extract text from PDF organized by page.
    
    Returns:
        List of {page_number, text, char_count} for each page
    """
    if not PDFPLUMBER_AVAILABLE:
        return []
    
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append({
                    "page_number": page_num,
                    "text": text,
                    "char_count": len(text)
                })
        
        logger.info(f"Extracted {len(pages)} pages from {pdf_path.name}")
        return pages
        
    except Exception as e:
        logger.error(f"Error extracting pages from {pdf_path}: {e}")
        return []
