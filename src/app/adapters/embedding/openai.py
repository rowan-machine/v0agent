# src/app/adapters/embedding/openai.py
"""
OpenAI Embedding Adapter

Implements EmbeddingPort interface using OpenAI's embedding API.
This is the primary production embedding provider.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from ...core.ports.embedding import EmbeddingPort

logger = logging.getLogger(__name__)


class OpenAIEmbeddingAdapter(EmbeddingPort):
    """
    OpenAI implementation of EmbeddingPort.
    
    Uses OpenAI's text-embedding-3-small model by default.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small"
    ):
        """
        Initialize OpenAI embedding adapter.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model to use
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model
        self._dimension = 1536  # Default for text-embedding-3-small
        self._client = None
        
        # Storage for embeddings (in production, use pgvector or similar)
        self._embeddings_store: Dict[str, Dict[str, Any]] = {}
        
        if not self._api_key:
            logger.warning("OpenAI API key not set - embedding generation will fail")
    
    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self._api_key)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client
    
    # =============================================================================
    # EMBEDDING GENERATION
    # =============================================================================
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text."""
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self._model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for multiple texts (batch)."""
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self._model,
                input=texts
            )
            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception as e:
            logger.error(f"Error generating embeddings batch: {e}")
            raise
    
    # =============================================================================
    # SIMILARITY OPERATIONS
    # =============================================================================
    
    def compute_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            a = np.array(embedding1)
            b = np.array(embedding2)
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0
    
    def find_similar(
        self,
        query_embedding: List[float],
        embeddings: List[Tuple[Any, List[float]]],
        top_k: int = 5,
        threshold: float = 0.5
    ) -> List[Tuple[Any, float]]:
        """Find most similar items from a list of embeddings."""
        results = []
        
        for id, embedding in embeddings:
            similarity = self.compute_similarity(query_embedding, embedding)
            if similarity >= threshold:
                results.append((id, similarity))
        
        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    # =============================================================================
    # VECTOR STORE OPERATIONS
    # =============================================================================
    
    def store_embedding(
        self,
        id: Any,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store an embedding with its ID and optional metadata."""
        try:
            self._embeddings_store[str(id)] = {
                "embedding": embedding,
                "metadata": metadata or {}
            }
            return True
        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            return False
    
    def search_similar(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar items using text query."""
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query)
            
            # Filter embeddings if needed
            embeddings_to_search = []
            for id, data in self._embeddings_store.items():
                if filters:
                    # Check if metadata matches filters
                    metadata = data.get("metadata", {})
                    matches = all(
                        metadata.get(k) == v 
                        for k, v in filters.items()
                    )
                    if not matches:
                        continue
                embeddings_to_search.append((id, data["embedding"]))
            
            # Find similar
            results = self.find_similar(query_embedding, embeddings_to_search, top_k)
            
            # Format results
            return [
                {
                    "id": id,
                    "score": score,
                    "metadata": self._embeddings_store.get(str(id), {}).get("metadata", {})
                }
                for id, score in results
            ]
        except Exception as e:
            logger.error(f"Error searching similar: {e}")
            return []
    
    def delete_embedding(self, id: Any) -> bool:
        """Delete an embedding by ID."""
        try:
            if str(id) in self._embeddings_store:
                del self._embeddings_store[str(id)]
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting embedding: {e}")
            return False
    
    # =============================================================================
    # CONFIGURATION
    # =============================================================================
    
    @property
    def embedding_dimension(self) -> int:
        """Return the dimension of embeddings this provider generates."""
        return self._dimension
    
    @property
    def model_name(self) -> str:
        """Return the name of the embedding model."""
        return self._model
    
    def is_available(self) -> bool:
        """Check if the embedding service is available."""
        return bool(self._api_key)
