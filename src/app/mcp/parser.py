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
]


def parse_meeting_summary(text: str) -> Dict[str, str]:
    """
    Parses Rowan-style meeting summaries.
    Extracts sections and <aside> blocks.
    """

    result = {}
    current_section = None
    buffer: List[str] = []

    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()

        # Section header
        if any(stripped.startswith(h) for h in SECTION_HEADERS):
            if current_section:
                result[current_section] = "\n".join(buffer).strip()
            current_section = stripped
            buffer = []
            continue

        # Ignore <aside> tags but keep content
        if stripped.startswith("<aside"):
            continue
        if stripped.endswith("</aside>"):
            continue

        buffer.append(line)

    if current_section:
        result[current_section] = "\n".join(buffer).strip()

    return result
