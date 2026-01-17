import re


def clean_meeting_text(text: str) -> str:
    """
    Clean meeting summary text by removing:
    - <aside> and </aside> tags
    - Markdown hash signs (###, ##, #)
    - Preserves the actual content
    """
    if not text:
        return text
    
    # Remove <aside> opening tags (with any attributes)
    text = re.sub(r'<aside[^>]*>', '', text)
    
    # Remove </aside> closing tags
    text = re.sub(r'</aside>', '', text)
    
    # Remove markdown headers (### at start of lines)
    # Keep the text, just remove the hash signs
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    
    # Clean up multiple consecutive blank lines (more than 2)
    text = re.sub(r'\n\n\n+', '\n\n', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text
