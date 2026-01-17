from typing import Callable, Dict

from .tools import (
    store_meeting_synthesis,
    store_doc,
    query_memory,
)

TOOL_REGISTRY: Dict[str, Callable] = {
    "store_meeting_synthesis": store_meeting_synthesis,
    "store_doc": store_doc,
    "query_memory": query_memory,
}
