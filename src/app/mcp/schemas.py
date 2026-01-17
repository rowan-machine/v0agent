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


class MCPCall(BaseModel):
    name: str
    args: dict
