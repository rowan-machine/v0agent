# sdk/signalflow/__init__.py
"""
SignalFlow SDK

A Python client library for the SignalFlow meeting intelligence platform.

Quick Start:
    ```python
    from signalflow import SignalFlowClient
    
    client = SignalFlowClient(api_url="http://localhost:8001")
    
    # List meetings
    meetings = client.meetings.list(limit=10)
    
    # Search signals
    signals = client.signals.search("action items")
    
    # Get DIKW pyramid
    pyramid = client.knowledge.get_pyramid()
    ```

For analytics and tracing:
    ```python
    from signalflow import AnalystClient
    
    analyst = AnalystClient()
    
    # Get trace feedback summary
    summary = analyst.get_feedback_summary(days=7)
    
    # Get agent performance
    perf = analyst.get_agent_performance("Arjuna")
    ```
"""

__version__ = "0.1.0"

from .client import SignalFlowClient
from .analyst import AnalystClient
from .models import (
    Meeting,
    Signal,
    Ticket,
    DIKWItem,
    CareerProfile,
    CareerSuggestion,
)

__all__ = [
    "SignalFlowClient",
    "AnalystClient",
    "Meeting",
    "Signal",
    "Ticket",
    "DIKWItem",
    "CareerProfile",
    "CareerSuggestion",
]
