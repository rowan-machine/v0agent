import os
import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests

DEFAULT_BASE_URL = "https://public.heypocketai.com"


class PocketClient:
    """Thin wrapper for Pocket Public API.

    Uses API key in Authorization header as either Bearer or ApiKey.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("POCKET_API_KEY")
        if not self.api_key:
            raise ValueError("Pocket API key not provided. Set POCKET_API_KEY env or pass api_key.")
        self.session = requests.Session()
        # Prefer Bearer format per docs, but ApiKey also allowed
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def list_recordings(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tag_ids: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "page": page,
            "limit": limit,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if tag_ids:
            params["tag_ids"] = tag_ids
        resp = self.session.get(self._url("/api/v1/public/recordings"), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_recording(self, recording_id: str, include_transcript: bool = True, include_summarizations: bool = True) -> Dict[str, Any]:
        params = {
            "include_transcript": include_transcript,
            "include_summarizations": include_summarizations,
        }
        resp = self.session.get(self._url(f"/api/v1/public/recordings/{recording_id}"), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_audio_url(self, recording_id: str, expires_in: int = 3600) -> Dict[str, Any]:
        params = {"expires_in": expires_in}
        resp = self.session.get(self._url(f"/api/v1/public/recordings/{recording_id}/audio-url"), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()


def _get_dict(d: Any) -> Dict[str, Any]:
    return d if isinstance(d, dict) else {}


def extract_latest_summary(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Extract the latest summary text from a recording detail response.

    The API returns summarizations as a dict with keys like 'v2_summary', 'v2_action_items', etc.
    Each summary version is a dict with 'markdown' and 'version' keys.
    
    We prefer v2 versions over v1, and pick the first available.
    Returns (summary_text, raw_summary_obj).
    """
    payload = _get_dict(data).get("data")
    rec = _get_dict(payload)

    # Debug: log what we see
    import sys
    summ_dict = _get_dict(rec.get("summarizations", {}))
    print(f"DEBUG: summarizations keys: {list(summ_dict.keys())}", file=sys.stderr)

    # Try to find a summary - prefer v2_summary, then v2_mind_map, then any v2, then any
    candidates = []
    for key in ["v2_summary", "v2_mind_map", "v1_summary", "summary"]:
        if key in summ_dict:
            candidates.append((key, summ_dict[key]))

    # If no match, just take first available
    if not candidates and summ_dict:
        candidates = [(k, v) for k, v in summ_dict.items()]

    for key, summ_obj in candidates:
        print(f"DEBUG: Checking {key}, type={type(summ_obj)}", file=sys.stderr)
        
        if isinstance(summ_obj, dict):
            # Try 'markdown' field first (v2 format)
            if "markdown" in summ_obj:
                text = summ_obj.get("markdown")
                if isinstance(text, str) and text.strip():
                    print(f"DEBUG: Found markdown in {key}, length={len(text)}", file=sys.stderr)
                    return text.strip(), summ_obj
            
            # Try other text fields
            for field in ("text", "content", "summary"):
                text = summ_obj.get(field)
                if isinstance(text, str) and text.strip():
                    print(f"DEBUG: Found {field} in {key}, length={len(text)}", file=sys.stderr)
                    return text.strip(), summ_obj
        
        elif isinstance(summ_obj, str) and summ_obj.strip():
            print(f"DEBUG: {key} is string, length={len(summ_obj)}", file=sys.stderr)
            return summ_obj.strip(), None

    print(f"DEBUG: No summary text found in any candidate", file=sys.stderr)
    return None, None


def extract_transcript_text(data: Dict[str, Any]) -> Optional[str]:
    """Extract transcript text with speaker labels from recording detail response.

    If segments are available, format as "SPEAKER_XX: text". Otherwise return plain text.
    Try keys: transcript.text, transcript.content, transcript_raw.
    """
    payload = _get_dict(data).get("data")
    rec = _get_dict(payload)
    transcript = rec.get("transcript")
    
    # Try to extract segments with speaker info
    if isinstance(transcript, dict):
        segments = transcript.get("segments")
        if isinstance(segments, list) and segments:
            # Format segments with speaker labels
            lines = []
            for seg in segments:
                if isinstance(seg, dict):
                    text = seg.get("text") or seg.get("originalText") or ""
                    speaker = seg.get("speaker") or "UNKNOWN"
                    if text:
                        lines.append(f"{speaker}: {text}")
            if lines:
                return "\n".join(lines)
        
        # Fallback to text/content fields
        for field in ("text", "content", "transcript_text"):
            val = transcript.get(field)
            if isinstance(val, str) and val.strip():
                return val.strip()
    elif isinstance(transcript, str) and transcript.strip():
        return transcript.strip()

    # Alternate shapes
    for key in ("transcript_raw", "raw_transcript"):
        val = rec.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def extract_mind_map(data: Dict[str, Any]) -> Optional[str]:
    """Extract mind map from summarizations.
    
    Looks for v2_mind_map in the summarizations dict.
    The mind map contains a 'nodes' array with structured nodes.
    Returns formatted text representation or None.
    """
    payload = _get_dict(data).get("data")
    rec = _get_dict(payload)
    summ_dict = _get_dict(rec.get("summarizations", {}))
    
    mind_map = _get_dict(summ_dict.get("v2_mind_map"))
    nodes = mind_map.get("nodes")
    
    if not isinstance(nodes, list) or not nodes:
        return None
    
    # Format nodes as hierarchical text
    lines = []
    for node in nodes:
        if isinstance(node, dict):
            title = node.get("title", "").strip()
            if not title:
                continue
            
            # Determine indent based on parent relationship
            node_id = node.get("node_id", "")
            parent_id = node.get("parent_node_id", "")
            
            # Simple heuristic: indent if not root
            indent = "  " if node_id != parent_id else ""
            lines.append(f"{indent}• {title}")
    
    if lines:
        return "\n".join(lines)
    
    return None


def extract_action_items(data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Extract action items from summarizations.
    
    Looks for v2_action_items.actionItems (list of action item objects).
    Each item has: description, assignee, priority, dueDate, etc.
    Returns list of action items or None.
    """
    payload = _get_dict(data).get("data")
    rec = _get_dict(payload)
    summ_dict = _get_dict(rec.get("summarizations", {}))
    
    action_items_obj = _get_dict(summ_dict.get("v2_action_items"))
    items = action_items_obj.get("actionItems")
    
    if isinstance(items, list) and items:
        return items
    
    return None


def get_all_summary_versions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all available summary versions from summarizations.
    
    Returns list of dicts with {key, text, version} for each available summary.
    Prefers v2_summary, v1_summary, etc.
    """
    payload = _get_dict(data).get("data")
    rec = _get_dict(payload)
    summ_dict = _get_dict(rec.get("summarizations", {}))
    
    versions = []
    # Look for v2_summary, v1_summary, summary, etc
    for key in ["v2_summary", "v1_summary", "summary"]:
        if key in summ_dict:
            summ_obj = _get_dict(summ_dict[key])
            # Try to extract text from markdown or other fields
            text = summ_obj.get("markdown") or summ_obj.get("text") or summ_obj.get("content")
            if isinstance(text, str) and text.strip():
                version = summ_obj.get("version", key)
                versions.append({
                    "key": key,
                    "text": text.strip(),
                    "version": version,
                    "label": f"{key.replace('_', ' ').title()} (v{version})"
                })
    
    return versions


def get_all_mind_map_versions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get all available mind map versions from summarizations.
    
    Returns list of dicts with {key, text, type} for each available mind map.
    Prefers v2_mind_map, v1_mind_map, etc.
    """
    payload = _get_dict(data).get("data")
    rec = _get_dict(payload)
    summ_dict = _get_dict(rec.get("summarizations", {}))
    
    versions = []
    # Look for v2_mind_map, v1_mind_map, mind_map, etc
    for key in ["v2_mind_map", "v1_mind_map", "mind_map"]:
        if key in summ_dict:
            mm_obj = _get_dict(summ_dict[key])
            
            # Format the mind map
            text = None
            if "nodes" in mm_obj and isinstance(mm_obj["nodes"], list):
                # Format nodes as hierarchical text
                lines = []
                for node in mm_obj["nodes"]:
                    if isinstance(node, dict):
                        title = node.get("title", "").strip()
                        if not title:
                            continue
                        node_id = node.get("node_id", "")
                        parent_id = node.get("parent_node_id", "")
                        indent = "  " if node_id != parent_id else ""
                        lines.append(f"{indent}• {title}")
                if lines:
                    text = "\n".join(lines)
            elif "markdown" in mm_obj:
                text = _get_dict(mm_obj).get("markdown")
            
            if text and isinstance(text, str) and text.strip():
                mm_type = mm_obj.get("type", key)
                versions.append({
                    "key": key,
                    "text": text.strip(),
                    "type": mm_type,
                    "label": f"{key.replace('_', ' ').title()}"
                })
    
    return versions
