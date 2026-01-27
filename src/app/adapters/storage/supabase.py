# src/app/adapters/storage/supabase.py
"""
Supabase Storage Adapter

Implements StoragePort interface using Supabase Storage.
"""

import os
import logging
from typing import Optional, Dict, Any
import uuid

from ...core.ports.storage import StoragePort

logger = logging.getLogger(__name__)


class SupabaseStorageAdapter(StoragePort):
    """
    Supabase implementation of StoragePort.
    
    Uses Supabase Storage for file operations.
    """
    
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        """
        Initialize Supabase storage adapter.
        
        Args:
            url: Supabase project URL (defaults to SUPABASE_URL env var)
            key: Supabase service key (defaults to SUPABASE_KEY env var)
        """
        self._url = url or os.getenv("SUPABASE_URL")
        self._key = key or os.getenv("SUPABASE_KEY")
        self._client = None
        
        if not self._url or not self._key:
            logger.warning("Supabase credentials not set - storage operations will fail")
    
    def _get_client(self):
        """Lazy initialization of Supabase client."""
        if self._client is None:
            from supabase import create_client
            self._client = create_client(self._url, self._key)
        return self._client
    
    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        bucket: str = "uploads",
        path: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload a file to Supabase Storage."""
        try:
            client = self._get_client()
            
            # Generate unique path if not provided
            if path is None:
                ext = os.path.splitext(filename)[1]
                path = f"{uuid.uuid4().hex}{ext}"
            
            # Ensure bucket exists (creates if not)
            try:
                client.storage.create_bucket(bucket, {"public": True})
            except Exception:
                pass  # Bucket likely already exists
            
            # Upload file
            file_options = {}
            if content_type:
                file_options["content-type"] = content_type
            
            result = client.storage.from_(bucket).upload(
                path=path,
                file=file_content,
                file_options=file_options
            )
            
            # Get public URL
            public_url = client.storage.from_(bucket).get_public_url(path)
            
            return {
                "url": public_url,
                "path": path,
                "bucket": bucket,
                "filename": filename,
                "size": len(file_content),
                "content_type": content_type
            }
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    def download_file(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> Optional[bytes]:
        """Download a file from Supabase Storage."""
        try:
            client = self._get_client()
            result = client.storage.from_(bucket).download(path)
            return result
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def delete_file(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> bool:
        """Delete a file from Supabase Storage."""
        try:
            client = self._get_client()
            client.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False
    
    def get_public_url(
        self,
        path: str,
        bucket: str = "uploads",
        expires_in: Optional[int] = None
    ) -> Optional[str]:
        """Get a public URL for a file."""
        try:
            client = self._get_client()
            if expires_in:
                # Generate signed URL
                result = client.storage.from_(bucket).create_signed_url(
                    path, expires_in
                )
                return result.get("signedURL")
            else:
                return client.storage.from_(bucket).get_public_url(path)
        except Exception as e:
            logger.error(f"Error getting public URL: {e}")
            return None
    
    def list_files(
        self,
        path: str = "",
        bucket: str = "uploads",
        limit: int = 100
    ) -> list:
        """List files in a storage path."""
        try:
            client = self._get_client()
            result = client.storage.from_(bucket).list(path, {"limit": limit})
            return result or []
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    def file_exists(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> bool:
        """Check if a file exists in storage."""
        try:
            client = self._get_client()
            # Try to get file info
            files = client.storage.from_(bucket).list(
                os.path.dirname(path) or "",
                {"search": os.path.basename(path)}
            )
            return any(f.get("name") == os.path.basename(path) for f in (files or []))
        except Exception:
            return False
    
    def get_file_metadata(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for a file."""
        try:
            client = self._get_client()
            files = client.storage.from_(bucket).list(
                os.path.dirname(path) or "",
                {"search": os.path.basename(path)}
            )
            for f in (files or []):
                if f.get("name") == os.path.basename(path):
                    return {
                        "name": f.get("name"),
                        "size": f.get("metadata", {}).get("size"),
                        "content_type": f.get("metadata", {}).get("mimetype"),
                        "created_at": f.get("created_at"),
                        "updated_at": f.get("updated_at")
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            return None
