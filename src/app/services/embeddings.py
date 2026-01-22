"""
Embedding service for SignalFlow using ChromaDB.
Handles text embeddings, semantic search, and vector storage.
"""

import chromadb
from chromadb.config import Settings
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Unified embedding service using ChromaDB.
    Supports in-process storage and fallback to HTTP client.
    """
    
    def __init__(
        self,
        persist_directory: str = "./chromadb_data",
        use_http_client: bool = False,
        http_host: str = "localhost",
        http_port: int = 8500,
    ):
        """
        Initialize embedding service.
        
        Args:
            persist_directory: Path for persistent storage (in-process mode)
            use_http_client: Use HTTP client instead of in-process
            http_host: HTTP server host (if using HTTP client)
            http_port: HTTP server port (if using HTTP client)
        """
        self.persist_directory = persist_directory
        self.use_http_client = use_http_client
        
        try:
            if use_http_client:
                # Connect to ChromaDB HTTP server
                logger.info(f"Connecting to ChromaDB HTTP server at {http_host}:{http_port}")
                self.client = chromadb.HttpClient(
                    host=http_host,
                    port=http_port,
                )
            else:
                # Use in-process persistent client
                logger.info(f"Using in-process ChromaDB with persistent storage at {persist_directory}")
                
                # Create directory if doesn't exist
                Path(persist_directory).mkdir(parents=True, exist_ok=True)
                
                self.client = chromadb.PersistentClient(path=persist_directory)
            
            # Create collections per entity type
            self._init_collections()
            
            logger.info("EmbeddingService initialized successfully")
        
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingService: {e}")
            raise
    
    def _init_collections(self):
        """Initialize ChromaDB collections."""
        collection_names = [
            "meetings",
            "documents",
            "signals",
            "dikw",
            "tickets",
            "career_memories",
        ]
        
        self.collections = {}
        for name in collection_names:
            try:
                self.collections[name] = self.client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"Initialized collection: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize collection {name}: {e}")
    
    def add_embedding(
        self,
        collection_name: str,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a text embedding to a collection.
        
        Args:
            collection_name: Name of collection (meetings, documents, etc.)
            doc_id: Unique document ID
            text: Text to embed
            metadata: Optional metadata to store with embedding
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection not found: {collection_name}")
        
        try:
            collection = self.collections[collection_name]
            collection.add(
                ids=[str(doc_id)],
                documents=[text],
                metadatas=[metadata or {}],
            )
            logger.debug(f"Added embedding to {collection_name}/{doc_id}")
        
        except Exception as e:
            logger.error(f"Failed to add embedding: {e}")
            raise
    
    def add_embeddings_batch(
        self,
        collection_name: str,
        doc_ids: List[str],
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Add multiple embeddings in batch.
        
        Args:
            collection_name: Name of collection
            doc_ids: List of document IDs
            texts: List of texts to embed
            metadatas: Optional list of metadata dicts
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection not found: {collection_name}")
        
        if len(doc_ids) != len(texts):
            raise ValueError("doc_ids and texts must have same length")
        
        try:
            collection = self.collections[collection_name]
            collection.add(
                ids=[str(d) for d in doc_ids],
                documents=texts,
                metadatas=metadatas or [{}] * len(doc_ids),
            )
            logger.info(f"Added {len(doc_ids)} embeddings to {collection_name}")
        
        except Exception as e:
            logger.error(f"Failed to add batch embeddings: {e}")
            raise
    
    def search(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Semantic search in a collection.
        
        Args:
            collection_name: Name of collection
            query_text: Text to search for
            top_k: Number of results to return
        
        Returns:
            Dictionary with ids, documents, distances, metadatas
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection not found: {collection_name}")
        
        try:
            collection = self.collections[collection_name]
            results = collection.query(
                query_texts=[query_text],
                n_results=top_k,
            )
            
            # Format results
            return {
                "ids": results["ids"][0] if results["ids"] else [],
                "documents": results["documents"][0] if results["documents"] else [],
                "distances": results["distances"][0] if results["distances"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            }
        
        except Exception as e:
            logger.error(f"Search failed in {collection_name}: {e}")
            return {"ids": [], "documents": [], "distances": [], "metadatas": []}
    
    def cross_collection_search(
        self,
        query_text: str,
        collections: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple collections.
        
        Args:
            query_text: Text to search for
            collections: List of collection names (all if None)
            top_k: Results per collection
        
        Returns:
            List of results with collection name included
        """
        search_collections = collections or list(self.collections.keys())
        all_results = []
        
        for collection_name in search_collections:
            if collection_name in self.collections:
                results = self.search(collection_name, query_text, top_k)
                
                # Add collection name to each result
                for i in range(len(results["ids"])):
                    all_results.append({
                        "collection": collection_name,
                        "id": results["ids"][i],
                        "document": results["documents"][i],
                        "distance": results["distances"][i],
                        "metadata": results["metadatas"][i],
                    })
        
        # Sort by distance (lower is better for cosine similarity)
        all_results.sort(key=lambda x: x["distance"])
        
        return all_results[:top_k]
    
    def delete_embedding(self, collection_name: str, doc_id: str) -> None:
        """
        Delete an embedding from a collection.
        
        Args:
            collection_name: Name of collection
            doc_id: Document ID to delete
        """
        if collection_name not in self.collections:
            raise ValueError(f"Collection not found: {collection_name}")
        
        try:
            collection = self.collections[collection_name]
            collection.delete(ids=[str(doc_id)])
            logger.debug(f"Deleted embedding from {collection_name}/{doc_id}")
        
        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}")
    
    def export_all(self) -> Dict[str, Any]:
        """
        Export all embeddings for backup/sync.
        
        Returns:
            Dictionary with all collections and their embeddings
        """
        export_data = {}
        
        for collection_name, collection in self.collections.items():
            try:
                data = collection.get()
                export_data[collection_name] = {
                    "ids": data["ids"],
                    "documents": data["documents"],
                    "metadatas": data["metadatas"],
                }
                logger.info(f"Exported {len(data['ids'])} embeddings from {collection_name}")
            
            except Exception as e:
                logger.error(f"Failed to export {collection_name}: {e}")
        
        return export_data
    
    def import_all(self, data: Dict[str, Any]) -> None:
        """
        Import embeddings from backup/sync.
        
        Args:
            data: Dictionary with collections and embeddings
        """
        for collection_name, collection_data in data.items():
            if collection_name not in self.collections:
                logger.warning(f"Collection not found for import: {collection_name}")
                continue
            
            try:
                collection = self.collections[collection_name]
                
                if collection_data.get("ids"):
                    collection.add(
                        ids=collection_data["ids"],
                        documents=collection_data.get("documents", []),
                        metadatas=collection_data.get("metadatas", []),
                    )
                    logger.info(f"Imported {len(collection_data['ids'])} embeddings to {collection_name}")
            
            except Exception as e:
                logger.error(f"Failed to import {collection_name}: {e}")
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get statistics on collections and embedding counts.
        
        Returns:
            Dictionary with stats per collection
        """
        stats = {}
        
        for collection_name, collection in self.collections.items():
            try:
                data = collection.get()
                stats[collection_name] = {
                    "embedding_count": len(data["ids"]),
                }
            except Exception as e:
                logger.error(f"Failed to get stats for {collection_name}: {e}")
                stats[collection_name] = {"error": str(e)}
        
        return stats
    
    def clear_collection(self, collection_name: str) -> None:
        """Clear all embeddings from a collection (for reprocessing)."""
        if collection_name not in self.collections:
            raise ValueError(f"Collection not found: {collection_name}")
        
        try:
            collection = self.collections[collection_name]
            data = collection.get()
            if data["ids"]:
                collection.delete(ids=data["ids"])
                logger.info(f"Cleared collection: {collection_name}")
        
        except Exception as e:
            logger.error(f"Failed to clear collection {collection_name}: {e}")


def create_embedding_service(
    persist_directory: str = "./chromadb_data",
    use_http_client: bool = False,
) -> EmbeddingService:
    """Factory function to create embedding service."""
    return EmbeddingService(
        persist_directory=persist_directory,
        use_http_client=use_http_client,
    )
