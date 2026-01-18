from typing import Callable, Dict

from .tools import (
    store_meeting_synthesis,
    store_doc,
    query_memory,
    load_meeting_bundle,
    collect_meeting_signals,
    get_meeting_signals,
    update_meeting_signals,
    export_meeting_signals,
    draft_summary_from_transcript,
)

TOOL_REGISTRY: Dict[str, Callable] = {
    "store_meeting_synthesis": store_meeting_synthesis,
    "store_doc": store_doc,
    "query_memory": query_memory,
    "load_meeting_bundle": load_meeting_bundle,
    "collect_meeting_signals": collect_meeting_signals,
    "get_meeting_signals": get_meeting_signals,
    "update_meeting_signals": update_meeting_signals,
    "export_meeting_signals": export_meeting_signals,
    "draft_summary_from_transcript": draft_summary_from_transcript,
}
