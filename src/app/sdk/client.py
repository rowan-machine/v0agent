# src/app/sdk/client.py
"""
SignalFlow SDK Client

Main entry point for the business analyst SDK.
Provides unified access to all data explorers and insight generation.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Environment:
    """SDK environment configuration."""
    name: str
    api_url: str
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None


# Predefined environments
ENVIRONMENTS = {
    "local": Environment(
        name="local",
        api_url="http://localhost:8001",
    ),
    "staging": Environment(
        name="staging", 
        api_url="https://v0agent-staging.up.railway.app",
    ),
    "production": Environment(
        name="production",
        api_url="https://v0agent-production.up.railway.app",
    ),
}


class SignalFlowClient:
    """
    Main SDK client for SignalFlow data exploration.
    
    Provides access to:
    - meetings: Meeting data explorer
    - signals: Signal search and analysis
    - career: Career development data
    - dikw: Knowledge hierarchy explorer
    - insights: AI-powered insight generation
    
    Example:
        ```python
        client = SignalFlowClient(environment="staging")
        
        # List recent meetings
        meetings = client.meetings.list(limit=10)
        
        # Search signals
        signals = client.signals.search("performance issues")
        
        # Generate insights
        insights = client.insights.summarize_week()
        ```
    """
    
    def __init__(
        self,
        environment: str = "staging",
        api_url: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        """
        Initialize the SDK client.
        
        Args:
            environment: One of "local", "staging", "production"
            api_url: Override the API URL
            supabase_url: Direct Supabase connection URL (optional)
            supabase_key: Supabase API key (optional)
        """
        # Load environment config
        if environment in ENVIRONMENTS:
            self._env = ENVIRONMENTS[environment]
        else:
            self._env = Environment(name=environment, api_url=api_url or "")
        
        # Allow overrides
        if api_url:
            self._env.api_url = api_url
        if supabase_url:
            self._env.supabase_url = supabase_url
        if supabase_key:
            self._env.supabase_key = supabase_key
        
        # Try to load from environment variables
        if not self._env.supabase_url:
            self._env.supabase_url = os.environ.get("SUPABASE_URL")
        if not self._env.supabase_key:
            self._env.supabase_key = os.environ.get("SUPABASE_KEY")
        
        # Initialize explorers lazily
        self._meetings = None
        self._signals = None
        self._career = None
        self._dikw = None
        self._insights = None
        self._supabase = None
        
        logger.info(f"SignalFlow SDK initialized for {self._env.name}")
    
    @property
    def meetings(self):
        """Get meetings explorer."""
        if self._meetings is None:
            from .explorers import MeetingsExplorer
            self._meetings = MeetingsExplorer(self)
        return self._meetings
    
    @property
    def signals(self):
        """Get signals explorer."""
        if self._signals is None:
            from .explorers import SignalsExplorer
            self._signals = SignalsExplorer(self)
        return self._signals
    
    @property
    def career(self):
        """Get career data explorer."""
        if self._career is None:
            from .explorers import CareerExplorer
            self._career = CareerExplorer(self)
        return self._career
    
    @property
    def dikw(self):
        """Get DIKW knowledge explorer."""
        if self._dikw is None:
            from .explorers import DIKWExplorer
            self._dikw = DIKWExplorer(self)
        return self._dikw
    
    @property
    def insights(self):
        """Get insights engine."""
        if self._insights is None:
            from .insights import InsightsEngine
            self._insights = InsightsEngine(self)
        return self._insights
    
    @property
    def supabase(self):
        """Get direct Supabase client (if configured)."""
        if self._supabase is None and self._env.supabase_url and self._env.supabase_key:
            try:
                from supabase import create_client
                self._supabase = create_client(
                    self._env.supabase_url,
                    self._env.supabase_key
                )
            except ImportError:
                logger.warning("supabase package not installed")
        return self._supabase
    
    def api_get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to API."""
        import requests
        url = f"{self._env.api_url}{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def api_post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request to API."""
        import requests
        url = f"{self._env.api_url}{endpoint}"
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status."""
        try:
            return self.api_get("/health")
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_feature_flags(self) -> Dict[str, Any]:
        """Get feature flag status."""
        return self.api_get("/api/settings/features")
    
    def run_diagnostics(self) -> Dict[str, Any]:
        """Run feature diagnostics."""
        return self.api_get("/api/settings/features/diagnostics")
    
    def __repr__(self):
        return f"SignalFlowClient(environment='{self._env.name}', api_url='{self._env.api_url}')"
