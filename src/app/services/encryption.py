"""
Encryption service for SignalFlow.
Handles client-side encryption before data is sent to Supabase.
All data is encrypted at rest and in transit.
"""

from cryptography.fernet import Fernet
import json
import logging
import base64
import hashlib
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EncryptionService:
    """Client-side encryption for secure cloud sync."""
    
    def __init__(self, master_key: str = None):
        """
        Initialize encryption service.
        
        Args:
            master_key: Base64-encoded Fernet key. If None, generates a new one.
                       Master key should be stored in SUPABASE_ENCRYPTION_KEY env var.
        """
        if master_key:
            try:
                self.cipher = Fernet(master_key.encode())
            except Exception as e:
                logger.error(f"Invalid encryption key format: {e}")
                raise ValueError("Encryption key must be valid base64-encoded Fernet key")
        else:
            # Generate new key
            self.cipher = Fernet(Fernet.generate_key())
            key_b64 = Fernet.generate_key().decode()
            logger.warning(f"Generated new encryption key. Store this in SUPABASE_ENCRYPTION_KEY: {key_b64}")
    
    def encrypt(self, data: Any) -> str:
        """
        Encrypt data before sending to cloud.
        
        Args:
            data: Python object to encrypt (will be JSON-encoded)
        
        Returns:
            Base64-encoded encrypted data
        """
        try:
            # Convert to JSON
            json_str = json.dumps(data)
            
            # Encrypt
            encrypted = self.cipher.encrypt(json_str.encode())
            
            # Return as base64 string
            return encrypted.decode()
        
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> Any:
        """
        Decrypt data downloaded from cloud.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
        
        Returns:
            Decrypted Python object
        """
        try:
            # Decrypt
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            
            # Parse JSON
            return json.loads(decrypted.decode())
        
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def hash_data(self, data: Any) -> str:
        """
        Generate content hash for change detection.
        
        Args:
            data: Data to hash
        
        Returns:
            SHA256 hash
        """
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key."""
        return Fernet.generate_key().decode()


class EncryptedPayload:
    """Wrapper for encrypted data with metadata."""
    
    def __init__(
        self,
        data: Any,
        encryption_service: EncryptionService,
        content_hash: str = None,
    ):
        """
        Create an encrypted payload.
        
        Args:
            data: Data to encrypt
            encryption_service: Encryption service instance
            content_hash: Optional content hash for change detection
        """
        self.encrypted_data = encryption_service.encrypt(data)
        self.content_hash = content_hash or encryption_service.hash_data(data)
        self.data_size = len(json.dumps(data))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Supabase storage."""
        return {
            "encrypted_data": self.encrypted_data,
            "content_hash": self.content_hash,
            "data_size": self.data_size,
        }
    
    @staticmethod
    def from_dict(payload_dict: Dict[str, Any], encryption_service: EncryptionService) -> Any:
        """Decrypt payload from dictionary."""
        return encryption_service.decrypt(payload_dict["encrypted_data"])


def create_encryption_service(encryption_key: str = None) -> EncryptionService:
    """
    Factory function to create encryption service.
    Loads key from environment or generates new one.
    """
    import os
    
    key = encryption_key or os.getenv("SUPABASE_ENCRYPTION_KEY")
    
    if not key:
        logger.warning("No encryption key provided. Generating new key...")
        key = EncryptionService.generate_key()
        logger.warning(f"Store this key in SUPABASE_ENCRYPTION_KEY: {key}")
    
    return EncryptionService(key)
