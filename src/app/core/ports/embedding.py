# src/app/core/ports/embedding.py
"""
Embedding Port Interface

Abstract interface for embedding/vector operations.
Implementations can be:
- OpenAIEmbeddingAdapter (production)
- LocalEmbeddingAdapter (privacy-focused, uses sentence-transformers)
- SupabaseVectorAdapter (pgvector via Supabase)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple


class EmbeddingPort(ABC):
    """
    Abstract port interface for embedding operations.
    
    All embedding adapters must implement this interface.
    This allows seamless switching between different embedding providers.
    """
    
    # =============================================================================
    # EMBEDDING GENERATION
    # =============================================================================
    
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        pass
    
    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts (batch).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        pass
    
    # =============================================================================
    # SIMILARITY OPERATIONS
    # =============================================================================
    
    @abstractmethod
    def compute_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1
        """
        pass
    
    @abstractmethod
    def find_similar(
        self,
        query_embedding: List[float],
        embeddings: List[Tuple[Any, List[float]]],  # (id, embedding)
        top_k: int = 5,
        threshold: float = 0.5
    ) -> List[Tuple[Any, float]]:
        """
        Find most similar items from a list of embeddings.
        
        Args:
            query_embedding: Query embedding vector
            embeddings: List of (id, embedding) tuples to search
            top_k: Number of results to return
            threshold: Minimum similarity score
            
        Returns:
            List of (id, similarity_score) tuples
        """
        pass
    
    # =============================================================================
    # VECTOR STORE OPERATIONS
    # =============================================================================
    
    @abstractmethod
    def store_embedding(
        self,
        id: Any,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store an embedding with its ID and optional metadata.
        
        Args:
            id: Unique identifier for the embedding
            embedding: Embedding vector
            metadata: Optional metadata to store with embedding
            
        Returns:
            True if stored successfully
        """
        pass
    
    @abstractmethod
    def search_similar(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar items using text query.
        
        This is the primary search interface - it handles:
        1. Generating query embedding
        2. Searching vector store
        3. Returning results with metadata
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filters: Optional filters on metadata
            
        Returns:
            List of results with id, score, and metadata
        """
        pass
    
    @abstractmethod
    def delete_embedding(self, id: Any) -> bool:
        """Delete an embedding by ID."""
        pass
    
    # =============================================================================
    # CONFIGURATION
    # =============================================================================
    
    @property
    @abstractmethod
    def embedding_dimension(self) -> int:
        """Return the dimension of embeddings this provider generates."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the embedding model."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the embedding service is available."""
        pass


class VectorStorePort(ABC):
    """
    Dedicated vector store interface for semantic search.
    
    Separates vector storage from embedding generation.
    Implementations:
    - SupabaseVectorStore (pgvector)
    - PineconeVectorStore
    - ChromaVectorStore
    - LocalFaissStore
    """
    
    @abstractmethod
    def upsert(
        self,
        id: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """Insert or update a vector."""
        pass
    
    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    def delete(self, ids: List[str], namespace: Optional[str] = None) -> int:
        """Delete vectors by IDs."""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        pass
