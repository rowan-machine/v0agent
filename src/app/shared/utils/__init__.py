# src/app/shared/utils/__init__.py
"""
Shared Utilities - Common helpers and utility functions

This module contains utilities used across multiple domains:
- File operations
- Date/time helpers
- String manipulation
- Validation helpers
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string in common formats."""
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%d/%m/%Y",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def days_ago(days: int) -> datetime:
    """Get datetime for N days ago."""
    return datetime.now() - timedelta(days=days)


def safe_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


__all__ = [
    "slugify",
    "truncate",
    "parse_date",
    "days_ago",
    "safe_get",
    "chunk_list",
]
