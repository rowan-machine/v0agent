# sdk/signalflow/async_client.py
"""
SignalFlow Async API Client

Async version of the SignalFlow client using httpx.AsyncClient.
Provides the same API as the sync client but with async/await support.
"""

import os
import logging
from typing import Optional, Dict, Any, List

import httpx

from .models import (
    Meeting,
    Signal,
    Ticket,
    DIKWItem,
    CareerProfile,
    CareerSuggestion,
    MeetingListResponse,
    SignalListResponse,
    TicketListResponse,
    DIKWPyramidResponse,
    SearchResponse,
    DIKWLevel,
    SignalType,
    TicketStatus,
)
from .client import Environment, ENVIRONMENTS

logger = logging.getLogger(__name__)


class AsyncMeetingsClient:
    """Async client for meeting operations."""
    
    def __init__(self, http: httpx.AsyncClient):
        self._http = http
    
    async def list(self, limit: int = 20, offset: int = 0) -> MeetingListResponse:
        """List meetings with pagination."""
        response = await self._http.get(
            "/api/v1/meetings",
            params={"limit": limit, "offset": offset}
        )
        response.raise_for_status()
        data = response.json()
        return MeetingListResponse(
            meetings=[Meeting(**m) for m in data.get("meetings", [])],
            count=data.get("count", 0)
        )
    
    async def get(self, meeting_id: str) -> Optional[Meeting]:
        """Get a single meeting by ID."""
        response = await self._http.get(f"/api/v1/meetings/{meeting_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return Meeting(**data.get("meeting", data))
    
    async def search(self, query: str, limit: int = 20) -> MeetingListResponse:
        """Search meetings by name or content."""
        response = await self._http.get(
            "/api/v1/meetings/search",
            params={"q": query, "limit": limit}
        )
        response.raise_for_status()
        data = response.json()
        return MeetingListResponse(
            meetings=[Meeting(**m) for m in data.get("meetings", [])],
            count=data.get("count", 0)
        )
    
    async def get_signals(self, meeting_id: str) -> SignalListResponse:
        """Get signals for a specific meeting."""
        response = await self._http.get(f"/api/v1/meetings/{meeting_id}/signals")
        response.raise_for_status()
        data = response.json()
        return SignalListResponse(
            signals=[Signal(**s) for s in data.get("signals", [])],
            count=data.get("count", 0)
        )


class AsyncSignalsClient:
    """Async client for signal operations."""
    
    def __init__(self, http: httpx.AsyncClient):
        self._http = http
    
    async def search(
        self,
        query: str,
        signal_type: Optional[SignalType] = None,
        limit: int = 20
    ) -> SignalListResponse:
        """Search signals across all meetings."""
        params = {"q": query, "limit": limit}
        if signal_type:
            params["type"] = signal_type.value
        
        response = await self._http.get("/api/v1/signals/search", params=params)
        response.raise_for_status()
        data = response.json()
        return SignalListResponse(
            signals=[Signal(**s) for s in data.get("signals", [])],
            count=data.get("count", 0)
        )
    
    async def list_recent(
        self,
        limit: int = 20,
        signal_type: Optional[SignalType] = None
    ) -> SignalListResponse:
        """List recent signals."""
        params = {"limit": limit}
        if signal_type:
            params["type"] = signal_type.value
        
        response = await self._http.get("/api/v1/signals/recent", params=params)
        response.raise_for_status()
        data = response.json()
        return SignalListResponse(
            signals=[Signal(**s) for s in data.get("signals", [])],
            count=data.get("count", 0)
        )


class AsyncTicketsClient:
    """Async client for ticket operations."""
    
    def __init__(self, http: httpx.AsyncClient):
        self._http = http
    
    async def list(
        self,
        status: Optional[TicketStatus] = None,
        in_sprint: Optional[bool] = None,
        limit: int = 50
    ) -> TicketListResponse:
        """List tickets with optional filters."""
        params = {"limit": limit}
        if status:
            params["status"] = status.value
        if in_sprint is not None:
            params["in_sprint"] = str(in_sprint).lower()
        
        response = await self._http.get("/api/v1/tickets", params=params)
        response.raise_for_status()
        data = response.json()
        return TicketListResponse(
            tickets=[Ticket(**t) for t in data.get("tickets", [])],
            count=data.get("count", 0)
        )
    
    async def get(self, ticket_id: str) -> Optional[Ticket]:
        """Get a single ticket by ID."""
        response = await self._http.get(f"/api/v1/tickets/{ticket_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return Ticket(**response.json())
    
    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        status: TicketStatus = TicketStatus.BACKLOG,
        priority: str = "medium"
    ) -> Ticket:
        """Create a new ticket."""
        response = await self._http.post(
            "/api/v1/tickets",
            json={
                "title": title,
                "description": description,
                "status": status.value,
                "priority": priority,
            }
        )
        response.raise_for_status()
        return Ticket(**response.json().get("ticket", response.json()))
    
    async def update_status(self, ticket_id: str, status: TicketStatus) -> Ticket:
        """Update ticket status."""
        response = await self._http.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"status": status.value}
        )
        response.raise_for_status()
        return Ticket(**response.json())


class AsyncKnowledgeClient:
    """Async client for DIKW knowledge operations."""
    
    def __init__(self, http: httpx.AsyncClient):
        self._http = http
    
    async def get_pyramid(self) -> DIKWPyramidResponse:
        """Get the full DIKW pyramid."""
        response = await self._http.get("/api/v1/dikw/pyramid")
        response.raise_for_status()
        data = response.json()
        return DIKWPyramidResponse(
            pyramid={
                level: [DIKWItem(**item) for item in items]
                for level, items in data.get("pyramid", {}).items()
            },
            counts=data.get("counts", {})
        )
    
    async def list_items(
        self,
        level: Optional[DIKWLevel] = None,
        status: str = "active",
        limit: int = 50
    ) -> List[DIKWItem]:
        """List DIKW items with optional filters."""
        params = {"status": status, "limit": limit}
        if level:
            params["level"] = level.value
        
        response = await self._http.get("/api/v1/dikw", params=params)
        response.raise_for_status()
        data = response.json()
        return [DIKWItem(**item) for item in data.get("items", [])]
    
    async def search(
        self,
        query: str,
        level: Optional[DIKWLevel] = None,
        limit: int = 20
    ) -> SearchResponse:
        """Search knowledge items."""
        params = {"q": query, "limit": limit}
        if level:
            params["level"] = level.value
        
        response = await self._http.get("/api/v1/dikw/search", params=params)
        response.raise_for_status()
        data = response.json()
        return SearchResponse(
            results=data.get("items", []),
            count=data.get("count", 0),
            query=query
        )


class AsyncCareerClient:
    """Async client for career development operations."""
    
    def __init__(self, http: httpx.AsyncClient):
        self._http = http
    
    async def get_profile(self) -> Optional[CareerProfile]:
        """Get the user's career profile."""
        response = await self._http.get("/api/v1/career/profile")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        if data.get("profile"):
            return CareerProfile(**data["profile"])
        return None
    
    async def get_suggestions(
        self,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[CareerSuggestion]:
        """Get career suggestions."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        
        response = await self._http.get("/api/v1/career/suggestions", params=params)
        response.raise_for_status()
        data = response.json()
        return [CareerSuggestion(**s) for s in data.get("suggestions", [])]


class AsyncSignalFlowClient:
    """
    Async SignalFlow API client.
    
    Provides typed async access to all SignalFlow resources.
    Same API as SignalFlowClient but with async/await support.
    
    Example:
        ```python
        async with AsyncSignalFlowClient(environment="staging") as client:
            # List recent meetings
            meetings = await client.meetings.list(limit=10)
            
            # Search for action items
            signals = await client.signals.search("TODO", signal_type=SignalType.ACTION_ITEM)
            
            # Get knowledge pyramid
            pyramid = await client.knowledge.get_pyramid()
        ```
    """
    
    def __init__(
        self,
        environment: str = "staging",
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the async SignalFlow client.
        
        Args:
            environment: One of "local", "staging", "production"
            api_url: Override the API URL
            api_key: API key for authentication (optional)
            timeout: Request timeout in seconds
        """
        # Resolve environment
        if environment in ENVIRONMENTS:
            self._env = ENVIRONMENTS[environment]
        else:
            self._env = Environment(name=environment, api_url=api_url or "")
        
        if api_url:
            self._env.api_url = api_url
        
        # Try environment variables
        if not self._env.api_url:
            self._env.api_url = os.environ.get("SIGNALFLOW_API_URL", "http://localhost:8001")
        
        api_key = api_key or os.environ.get("SIGNALFLOW_API_KEY")
        
        # Setup HTTP client
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        self._http = httpx.AsyncClient(
            base_url=self._env.api_url,
            headers=headers,
            timeout=timeout,
        )
        
        # Initialize sub-clients
        self.meetings = AsyncMeetingsClient(self._http)
        self.signals = AsyncSignalsClient(self._http)
        self.tickets = AsyncTicketsClient(self._http)
        self.knowledge = AsyncKnowledgeClient(self._http)
        self.career = AsyncCareerClient(self._http)
        
        logger.info(f"AsyncSignalFlowClient initialized for {self._env.name} ({self._env.api_url})")
    
    async def health(self) -> Dict[str, Any]:
        """Check API health status."""
        response = await self._http.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        await self._http.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
