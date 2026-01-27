# src/app/adapters/embedding/local.py
"""
Local Embedding Adapter

Implements EmbeddingPort interface using sentence-transformers locally.
Ideal for privacy-focused deployments without external API calls.
"""

import logging
import numpy as np
from typing import List, Optional, Dict, Any, Tuple

from ...core.ports.embedding import EmbeddingPort

logger = logging.getLogger(__name__)


class LocalEmbeddingAdapter(EmbeddingPort):
    """
    Local implementation of EmbeddingPort using sentence-transformers.
    
    Generates embeddings locally without external API calls.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize local embedding adapter.
        
        Args:
            model_name: Sentence transformer model name
        """
        self._model_name = model_name
        self._model = None
        self._dimension = None
    
    def _get_model(self):
        """Lazy initialization of sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                # Get embedding dimension from model
                test_embedding = self._model.encode(["test"])[0]
                self._dimension = len(test_embedding)
                logger.info(f"Loaded local embedding model: {self._model_name} (dim={self._dimension})")
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model
    
    @property
    def dimension(self) -> int:
        """Get the embedding dimension for this model."""
        if self._dimension is None:
            self._get_model()  # Initialize to get dimension
        return self._dimension or 384  # Default for MiniLM
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            model = self._get_model()
            embedding = model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating local embedding: {e}")
            raise
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            model = self._get_model()
            embeddings = model.encode(texts)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error generating local embeddings: {e}")
            raise
    
    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            a = np.array(embedding1)
            b = np.array(embedding2)
            
            # Cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def find_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[Tuple[str, List[float]]],
        top_k: int = 10,
        threshold: float = 0.0
    ) -> List[Tuple[str, float]]:
        """Find similar items from candidates."""
        try:
            results = []
            query_vec = np.array(query_embedding)
            query_norm = np.linalg.norm(query_vec)
            
            if query_norm == 0:
                return results
            
            for item_id, candidate_embedding in candidate_embeddings:
                candidate_vec = np.array(candidate_embedding)
                candidate_norm = np.linalg.norm(candidate_vec)
                
                if candidate_norm == 0:
                    continue
                
                similarity = float(np.dot(query_vec, candidate_vec) / (query_norm * candidate_norm))
                
                if similarity >= threshold:
                    results.append((item_id, similarity))
            
            # Sort by similarity descending
            results.sort(key=lambda x: x[1], reverse=True)
            
            return results[:top_k]
        except Exception as e:
            logger.error(f"Error finding similar items: {e}")
            return []
    
    def store_embedding(
        self,
        item_id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        table: str = "embeddings"
    ) -> bool:
        """
        Store embedding - delegates to database adapter.
        
        Note: Local embeddings don't have built-in storage.
        Use the database adapter's embedding storage instead.
        """
        logger.warning(
            "LocalEmbeddingAdapter.store_embedding called - "
            "embeddings should be stored via database adapter"
        )
        return False
    
    def search_similar(
        self,
        query_text: str,
        table: str = "embeddings",
        match_count: int = 10,
        match_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar items by text - requires database integration.
        
        Note: For local embeddings, this would need to:
        1. Generate query embedding
        2. Fetch all embeddings from database
        3. Compute similarities locally
        
        This is handled at the service layer, not here.
        """
        logger.warning(
            "LocalEmbeddingAdapter.search_similar called - "
            "similarity search should be performed at service layer"
        )
        return []
