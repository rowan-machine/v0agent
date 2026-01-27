# src/app/core/ports/storage.py
"""
Storage Port Interface

Abstract interface for file storage operations.
Implementations can be:
- SupabaseStorageAdapter (production)
- LocalStorageAdapter (local development)
- S3StorageAdapter (AWS)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, BinaryIO


class StoragePort(ABC):
    """
    Abstract port interface for file storage operations.
    
    All storage adapters must implement this interface.
    This allows seamless switching between different storage backends.
    """
    
    @abstractmethod
    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        bucket: str = "uploads",
        path: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to storage.
        
        Args:
            file_content: Raw file bytes
            filename: Name of the file
            bucket: Storage bucket name
            path: Optional path within bucket
            content_type: MIME type of the file
            metadata: Optional metadata to store with file
            
        Returns:
            Dict with 'url', 'path', and other storage info
        """
        pass
    
    @abstractmethod
    def download_file(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> Optional[bytes]:
        """
        Download a file from storage.
        
        Args:
            path: Path to the file in storage
            bucket: Storage bucket name
            
        Returns:
            File content as bytes, or None if not found
        """
        pass
    
    @abstractmethod
    def delete_file(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> bool:
        """
        Delete a file from storage.
        
        Args:
            path: Path to the file in storage
            bucket: Storage bucket name
            
        Returns:
            True if deleted successfully
        """
        pass
    
    @abstractmethod
    def get_public_url(
        self,
        path: str,
        bucket: str = "uploads",
        expires_in: Optional[int] = None
    ) -> Optional[str]:
        """
        Get a public URL for a file.
        
        Args:
            path: Path to the file in storage
            bucket: Storage bucket name
            expires_in: Optional expiration time in seconds (for signed URLs)
            
        Returns:
            Public URL string, or None if not available
        """
        pass
    
    @abstractmethod
    def list_files(
        self,
        path: str = "",
        bucket: str = "uploads",
        limit: int = 100
    ) -> list:
        """
        List files in a storage path.
        
        Args:
            path: Path prefix to list
            bucket: Storage bucket name
            limit: Maximum number of files to return
            
        Returns:
            List of file metadata dicts
        """
        pass
    
    @abstractmethod
    def file_exists(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            path: Path to the file
            bucket: Storage bucket name
            
        Returns:
            True if file exists
        """
        pass
    
    @abstractmethod
    def get_file_metadata(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file.
        
        Args:
            path: Path to the file
            bucket: Storage bucket name
            
        Returns:
            Dict with file metadata (size, content_type, created_at, etc.)
        """
        pass
