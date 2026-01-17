import re
from typing import Dict, List


SECTION_HEADERS = [
    "Summarized notes",
    "Work Identified",
    "Outcomes",
    "Context",
    "Key Signal",
    "Notes",
    "Synthesized Signals",
    "Risks / Open Questions",
    "Screenshots / Photos",
    "Notes (raw)",
    "Commitments / Ideas",
    "Commitments",
    "Ideas",
]


def parse_meeting_summary(text: str) -> Dict[str, str]:
    """
    Parses Rowan-style meeting summaries.
    Extracts sections with or without markdown headers.
    Handles both ### prefixed headers and plain text headers.
    """

    result = {}
    current_section = None
    buffer: List[str] = []

    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        
        if not stripped:
            buffer.append(line)
            continue

        # Remove markdown prefix, bold markers, and clean up
        cleaned_header = stripped.lstrip("#").strip().strip("*").strip()
        
        # Check if this line is a section header
        # Match by checking if cleaned_header starts with any known section header
        matched_header = None
        for header in SECTION_HEADERS:
            if cleaned_header.startswith(header):
                matched_header = cleaned_header
                break
        
        if matched_header:
            # Save previous section
            if current_section:
                result[current_section] = "\n".join(buffer).strip()
            current_section = matched_header
            buffer = []
            continue

        # Ignore <aside> tags but keep content
        if stripped.startswith("<aside"):
            continue
        if stripped.endswith("</aside>"):
            continue

        buffer.append(line)

    # Save final section
    if current_section:
        result[current_section] = "\n".join(buffer).strip()

    return result
