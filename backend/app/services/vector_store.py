"""FAISS vector store service for document embeddings and similarity search"""

from pathlib import Path
from typing import List, Optional
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import LibraryItem


class VectorStoreService:
    """FAISS-based vector store for document chunks"""
    
    def __init__(self):
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.dimension = 384  # Dimension for all-MiniLM-L6-v2
    
    def _get_index_path(self, project_id: str) -> Path:
        """Get path to project's FAISS index"""
        return settings.faiss_index_path / f"{project_id}.index"
    
    def _get_metadata_path(self, project_id: str) -> Path:
        """Get path to project's chunk metadata"""
        return settings.faiss_index_path / f"{project_id}_metadata.npy"
    
    def create_index(
        self,
        project_id: str,
        chunks: List[str],
        paper_ids: List[str]
    ) -> str:
        """Create or update FAISS index for project
        
        Args:
            project_id: Project ID
            chunks: List of text chunks
            paper_ids: Corresponding paper IDs for each chunk
            
        Returns:
            Path to saved index
        """
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        index = faiss.IndexFlatL2(self.dimension)
        index.add(embeddings)
        
        # Save index
        index_path = self._get_index_path(project_id)
        faiss.write_index(index, str(index_path))
        
        # Save metadata (chunk text + paper IDs)
        metadata = np.array([
            {"chunk": chunk, "paper_id": paper_id}
            for chunk, paper_id in zip(chunks, paper_ids)
        ])
        metadata_path = self._get_metadata_path(project_id)
        np.save(metadata_path, metadata)
        
        return str(index_path)
    
    async def search_similar(
        self,
        project_id: str,
        query: str,
        paper_ids: Optional[List[str]] = None,
        top_k: int = 5,
        include_metadata: bool = False
    ) -> List:
        """Search for similar chunks in project's vector store
        
        Args:
            project_id: Project ID
            query: Search query
            paper_ids: Optional filter to specific papers
            top_k: Number of results to return
            include_metadata: If True, returns dicts with chunk text and metadata (page_number, etc.)
            
        Returns:
            List of text chunks (or dicts with metadata if include_metadata=True)
        """
        
        index_path = self._get_index_path(project_id)
        metadata_path = self._get_metadata_path(project_id)
        
        # Check if index exists
        if not index_path.exists():
            return []
        
        # Load index and metadata
        index = faiss.read_index(str(index_path))
        metadata = np.load(metadata_path, allow_pickle=True)
        
        # Encode query
        query_embedding = self.embedding_model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')
        
        # Search (get more candidates to allow filtering)
        distances, indices = index.search(query_embedding, min(top_k * 5, len(metadata)))
        
        # Filter by paper IDs if provided
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(metadata):
                chunk_meta = metadata[idx].item()
                
                # Check type (paper vs chat)
                item_type = chunk_meta.get("type", "paper")
                
                # If paper_ids provided, ONLY show papers in that list
                # BUT if we want "Unified Memory", we might want to allow relevant CHAT logs too?
                # For now, let's say if paper_ids is explicit, we strictly filter papers, 
                # UNLESS paper_ids=['*'] or similar wildcard is used for "global context"
                
                if paper_ids:
                    if item_type == "paper":
                        if chunk_meta.get("paper_id") not in paper_ids:
                            continue
                    else:
                        # It's a chat log. Do we include it?
                        # If strict paper search, maybe not.
                        # But for "RAG Response", we likely want it.
                        # Let's assume if paper_ids is passed, we focus on papers.
                        # We need a flag to enable chat history.
                        pass # Currently ignores chat logs if paper_ids set?
                        # Actually, let's include chat logs if they are relevant, 
                        # but usually retrieval is driven by "selected papers".
                        # Use heuristics: if relevant score is high, include it?
                        # For now, simplistic filter:
                        if item_type == "chat":
                            pass # Allow chat by default? Or filter out?
                            # Let's FILTER OUT chat if paper_ids are strict
                            # unless we explicitly ask for history.
                            # Changing logic: if paper_ids is set, we only look at papers.
                            continue

                if include_metadata:
                    # Return full metadata including page number
                    results.append({
                        "text": chunk_meta["chunk"],
                        "paper_id": chunk_meta.get("paper_id"),
                        "page_number": chunk_meta.get("page_number"),
                        "type": item_type,
                        "session_id": chunk_meta.get("session_id"),
                        "relevance_score": float(distances[0][i]) if i < len(distances[0]) else 0.0
                    })
                else:
                    results.append(chunk_meta["chunk"])
                
                if len(results) >= top_k:
                    break
        
        return results
    
    def add_document_chunks(
        self,
        project_id: str,
        paper_id: str,
        chunks: List[str]
    ):
        """Add chunks from a new document to existing index (no page tracking)"""
        
        index_path = self._get_index_path(project_id)
        metadata_path = self._get_metadata_path(project_id)
        
        # Load existing or create new
        if index_path.exists():
            index = faiss.read_index(str(index_path))
            metadata = list(np.load(metadata_path, allow_pickle=True))
        else:
            index = faiss.IndexFlatL2(self.dimension)
            metadata = []
        
        # Encode new chunks
        embeddings = self.embedding_model.encode(chunks, show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')
        
        # Add to index
        index.add(embeddings)
        
        # Add metadata
        for chunk in chunks:
            metadata.append({"chunk": chunk, "paper_id": paper_id})
        
        # Save updated index
        faiss.write_index(index, str(index_path))
        np.save(metadata_path, np.array(metadata))
    
    def add_document_chunks_with_pages(
        self,
        project_id: str,
        paper_id: str,
        chunks_with_pages: List[dict]
    ):
        """
        Add chunks with page number tracking for PDF-to-page linking.
        
        Args:
            project_id: Project ID
            paper_id: Paper ID
            chunks_with_pages: List of {text, page_number, ...} dicts from chunk_pdf_with_pages()
        """
        
        index_path = self._get_index_path(project_id)
        metadata_path = self._get_metadata_path(project_id)
        
        # Load existing or create new
        if index_path.exists():
            index = faiss.read_index(str(index_path))
            metadata = list(np.load(metadata_path, allow_pickle=True))
        else:
            index = faiss.IndexFlatL2(self.dimension)
            metadata = []
        
        # Extract texts for encoding
        texts = [c["text"] for c in chunks_with_pages]
        
        # Encode new chunks
        embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')
        
        # Add to index
        index.add(embeddings)
        
        # Add metadata WITH PAGE NUMBERS
        for chunk in chunks_with_pages:
            metadata.append({
                "chunk": chunk["text"],
                "paper_id": paper_id,
                "page_number": chunk.get("page_number"),  # ← KEY: Store page number
                "source_file": chunk.get("source_file")
            })
        
        # Save updated index
        faiss.write_index(index, str(index_path))
        np.save(metadata_path, np.array(metadata))

    def add_chat_interaction(
        self,
        project_id: str,
        session_id: str,
        user_message: str,
        ai_response: str
    ):
        """Index a chat interaction for long-term memory"""
        index_path = self._get_index_path(project_id)
        metadata_path = self._get_metadata_path(project_id)
        
        # Load existing
        if index_path.exists():
            index = faiss.read_index(str(index_path))
            metadata = list(np.load(metadata_path, allow_pickle=True))
        else:
            index = faiss.IndexFlatL2(self.dimension)
            metadata = []
            
        # Create text to index (User Q + AI A)
        interaction_text = f"User: {user_message}\nAI: {ai_response}"
        
        # Encode
        embeddings = self.embedding_model.encode([interaction_text], show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')
        
        index.add(embeddings)
        
        # Add metadata with type=chat
        metadata.append({
            "chunk": interaction_text,
            "type": "chat",
            "session_id": session_id,
            "project_id": project_id,
            "timestamp": str(datetime.utcnow())
        })
        
        # Save
        faiss.write_index(index, str(index_path))
        np.save(metadata_path, np.array(metadata))


# Global service instance
vector_store = VectorStoreService()
