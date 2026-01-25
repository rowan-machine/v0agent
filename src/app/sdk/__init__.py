# src/app/sdk/__init__.py
"""
SignalFlow Business Domain Analyst SDK

A Python SDK for exploring and analyzing SignalFlow data via Jupyter notebooks.
Provides high-level abstractions for data scientists to explore meetings,
signals, career data, and generate AI-powered insights.

Usage:
    from src.app.sdk import SignalFlowClient
    
    # Connect to staging (default) or production
    client = SignalFlowClient(environment="staging")
    
    # Explore data
    meetings = client.meetings.list()
    signals = client.signals.search("architecture decisions")
    
    # Generate insights
    insights = client.insights.generate_for_meetings(meetings)
"""

from .client import SignalFlowClient
from .explorers import (
    MeetingsExplorer,
    SignalsExplorer,
    CareerExplorer,
    DIKWExplorer,
)
from .insights import InsightsEngine

__all__ = [
    "SignalFlowClient",
    "MeetingsExplorer",
    "SignalsExplorer", 
    "CareerExplorer",
    "DIKWExplorer",
    "InsightsEngine",
]
