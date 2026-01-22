"""
Configuration loader for SignalFlow.
Loads configuration from YAML files and environment variables.
Supports hot-reloading in development mode.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import os
from dataclasses import dataclass, field
from pydantic import BaseModel
import logging
import uuid

logger = logging.getLogger(__name__)


class SyncConfig(BaseModel):
    """Multi-device synchronization configuration."""
    
    # Local network sync (mDNS)
    use_mdns: bool = True
    mdns_discovery_timeout: int = 1  # seconds
    
    # Cloud backup via Supabase
    enable_supabase: bool = True
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_encryption_key: str = ""
    auto_sync_interval: int = 300  # 5 minutes
    
    # Mobile sync
    mobile_enabled: bool = True
    mobile_sync_interval: int = 300
    mobile_cache_size_mb: int = 100
    
    # Conflict resolution
    conflict_resolution: str = "last-write-wins"
    
    class Config:
        extra = "allow"


class SignalFlowConfig(BaseModel):
    """Main SignalFlow configuration."""
    
    # Environment
    environment: str = "development"
    debug: bool = True
    
    # Device identification
    device_id: str = ""  # Auto-generated if empty
    device_name: str = "signalflow-device"
    device_type: str = "desktop"  # desktop, mobile, web
    
    # Agents
    agents: Dict[str, Any] = field(default_factory=dict)
    
    # Sync
    sync: SyncConfig = field(default_factory=SyncConfig)
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_prefix: str = "/api"
    
    # Database
    database_path: str = "agent.db"
    
    # Embeddings
    embeddings_db_path: str = "./chromadb_data"
    embeddings_model: str = "text-embedding-3-small"
    
    # Logging
    log_level: str = "INFO"
    
    # Legacy (keep for compatibility)
    DB_PATH: str = "agent.db"
    OPENAI_API_KEY: str = ""
    
    class Config:
        extra = "allow"


class ConfigLoader:
    """Load and manage SignalFlow configuration."""
    
    def __init__(self, config_dir: str = "config"):
        """
        Initialize config loader.
        
        Args:
            config_dir: Directory containing config files
        """
        self.config_dir = Path(config_dir)
        self.config: Optional[SignalFlowConfig] = None
        self.load()
    
    def load(self) -> SignalFlowConfig:
        """Load configuration from YAML and environment variables."""
        
        # Determine which config file to load
        env = os.getenv("SIGNALFLOW_ENV", "development")
        config_file = self.config_dir / f"{env}.yaml"
        
        # Load default config first
        default_config = self._load_yaml(self.config_dir / "default.yaml")
        
        # Override with environment-specific config
        if config_file.exists():
            env_config = self._load_yaml(config_file)
            default_config.update(env_config)
        else:
            logger.warning(f"Config file not found: {config_file}, using defaults")
        
        # Override with environment variables
        default_config.update(self._load_from_env())
        
        # Auto-generate device_id if not set
        if not default_config.get("device_id"):
            default_config["device_id"] = str(uuid.uuid4())
        
        # Create config object
        self.config = SignalFlowConfig(**default_config)
        
        logger.info(f"Configuration loaded (environment: {env}, device_id: {self.config.device_id})")
        
        return self.config
    
    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML config file."""
        if not path.exists():
            return {}
        
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f)
                return data or {}
        except Exception as e:
            logger.error(f"Failed to load YAML config {path}: {e}")
            return {}
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # Device configuration
        if device_id := os.getenv("SIGNALFLOW_DEVICE_ID"):
            config["device_id"] = device_id
        if device_name := os.getenv("SIGNALFLOW_DEVICE_NAME"):
            config["device_name"] = device_name
        if device_type := os.getenv("SIGNALFLOW_DEVICE_TYPE"):
            config["device_type"] = device_type
        
        # Sync configuration
        sync = {}
        if mdns := os.getenv("SIGNALFLOW_MDNS_ENABLED"):
            sync["use_mdns"] = mdns.lower() == "true"
        if supabase_url := os.getenv("SUPABASE_URL"):
            sync["supabase_url"] = supabase_url
        if supabase_key := os.getenv("SUPABASE_KEY"):
            sync["supabase_key"] = supabase_key
        if supabase_encryption_key := os.getenv("SUPABASE_ENCRYPTION_KEY"):
            sync["supabase_encryption_key"] = supabase_encryption_key
        
        if sync:
            config["sync"] = sync
        
        # API configuration
        if api_port := os.getenv("SIGNALFLOW_API_PORT"):
            config["api_port"] = int(api_port)
        
        # Legacy support
        if openai_key := os.getenv("OPENAI_API_KEY"):
            config["OPENAI_API_KEY"] = openai_key
        if db_path := os.getenv("AGENT_DB_PATH"):
            config["database_path"] = db_path
            config["DB_PATH"] = db_path
        
        return config
    
    def get(self) -> SignalFlowConfig:
        """Get current configuration."""
        if not self.config:
            self.load()
        return self.config
    
    def reload(self):
        """Reload configuration (useful for development)."""
        logger.info("Reloading configuration...")
        self.load()


# Global config instance
_global_config_loader: Optional[ConfigLoader] = None


def get_config() -> SignalFlowConfig:
    """Get the global SignalFlow configuration."""
    global _global_config_loader
    if _global_config_loader is None:
        _global_config_loader = ConfigLoader()
    return _global_config_loader.get()


def initialize_config(config_dir: str = "config") -> SignalFlowConfig:
    """Initialize the global configuration loader."""
    global _global_config_loader
    _global_config_loader = ConfigLoader(config_dir)
    return _global_config_loader.get()


# Legacy compatibility
DB_PATH = os.getenv("AGENT_DB_PATH", "agent.db")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Updated from gpt-5
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")