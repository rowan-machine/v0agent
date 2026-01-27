# src/app/adapters/storage/local.py
"""
Local File Storage Adapter

Implements StoragePort interface using local filesystem.
"""

import os
import shutil
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ...core.ports.storage import StoragePort

logger = logging.getLogger(__name__)


class LocalStorageAdapter(StoragePort):
    """
    Local filesystem implementation of StoragePort.
    
    Stores files on the local filesystem for privacy-focused deployments.
    """
    
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize local storage adapter.
        
        Args:
            base_path: Base directory for file storage (defaults to ./uploads)
        """
        self._base_path = Path(base_path or os.getenv("LOCAL_STORAGE_PATH", "./uploads"))
        self._base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_bucket_path(self, bucket: str) -> Path:
        """Get the path for a bucket, creating if necessary."""
        bucket_path = self._base_path / bucket
        bucket_path.mkdir(parents=True, exist_ok=True)
        return bucket_path
    
    def _get_file_path(self, bucket: str, path: str) -> Path:
        """Get the full path for a file."""
        return self._get_bucket_path(bucket) / path
    
    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        bucket: str = "uploads",
        path: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Upload a file to local storage."""
        try:
            # Generate unique path if not provided
            if path is None:
                ext = os.path.splitext(filename)[1]
                path = f"{uuid.uuid4().hex}{ext}"
            
            file_path = self._get_file_path(bucket, path)
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            # Store metadata if provided
            if metadata:
                meta_path = file_path.with_suffix(file_path.suffix + ".meta")
                import json
                with open(meta_path, "w") as f:
                    json.dump(metadata, f)
            
            # Generate local URL (file:// scheme)
            local_url = f"file://{file_path.absolute()}"
            
            return {
                "url": local_url,
                "path": path,
                "bucket": bucket,
                "filename": filename,
                "size": len(file_content),
                "content_type": content_type or mimetypes.guess_type(filename)[0]
            }
        except Exception as e:
            logger.error(f"Error uploading file locally: {e}")
            raise
    
    def download_file(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> Optional[bytes]:
        """Download a file from local storage."""
        try:
            file_path = self._get_file_path(bucket, path)
            if file_path.exists():
                with open(file_path, "rb") as f:
                    return f.read()
            return None
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            return None
    
    def delete_file(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> bool:
        """Delete a file from local storage."""
        try:
            file_path = self._get_file_path(bucket, path)
            if file_path.exists():
                file_path.unlink()
            # Also delete metadata file if exists
            meta_path = file_path.with_suffix(file_path.suffix + ".meta")
            if meta_path.exists():
                meta_path.unlink()
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
        """Get a URL for a file (local file:// URL)."""
        try:
            file_path = self._get_file_path(bucket, path)
            if file_path.exists():
                return f"file://{file_path.absolute()}"
            return None
        except Exception as e:
            logger.error(f"Error getting file URL: {e}")
            return None
    
    def list_files(
        self,
        path: str = "",
        bucket: str = "uploads",
        limit: int = 100
    ) -> list:
        """List files in a storage path."""
        try:
            search_path = self._get_bucket_path(bucket)
            if path:
                search_path = search_path / path
            
            if not search_path.exists():
                return []
            
            files = []
            for item in search_path.iterdir():
                if item.is_file() and not item.name.endswith(".meta"):
                    stat = item.stat()
                    files.append({
                        "name": item.name,
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    if len(files) >= limit:
                        break
            
            return files
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
            file_path = self._get_file_path(bucket, path)
            return file_path.exists()
        except Exception:
            return False
    
    def get_file_metadata(
        self,
        path: str,
        bucket: str = "uploads"
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for a file."""
        try:
            file_path = self._get_file_path(bucket, path)
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            metadata = {
                "name": file_path.name,
                "size": stat.st_size,
                "content_type": mimetypes.guess_type(file_path.name)[0],
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            }
            
            # Load custom metadata if exists
            meta_path = file_path.with_suffix(file_path.suffix + ".meta")
            if meta_path.exists():
                import json
                with open(meta_path, "r") as f:
                    metadata["custom"] = json.load(f)
            
            return metadata
        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            return None
