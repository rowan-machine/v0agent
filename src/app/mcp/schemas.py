from pydantic import BaseModel, Field
from typing import Optional, Literal, List


class StoreMeetingInput(BaseModel):
    meeting_name: str
    synthesized_notes: str
    meeting_date: Optional[str] = None


class StoreDocInput(BaseModel):
    source: str
    content: str
    document_date: Optional[str] = None


class QueryMemoryInput(BaseModel):
    question: str
    source_type: Literal["docs", "meetings", "both"] = "both"
    limit: int = 6


class CollectSignalsInput(BaseModel):
    signal_type: Literal["decisions", "action_items", "blockers", "risks", "ideas", "key_signals", "all"] = "all"
    limit: int = 50


class GetMeetingSignalsInput(BaseModel):
    meeting_id: int


class UpdateMeetingSignalsInput(BaseModel):
    meeting_id: Optional[int] = None
    force: bool = False


class MCPCall(BaseModel):
    name: str
    args: dict

class LoadMeetingBundleInput(BaseModel):
    meeting_name: str
    meeting_date: str | None = None
    summary_text: str
    transcript_text: str | None = None
    format: Literal["plain", "json"] = "plain"