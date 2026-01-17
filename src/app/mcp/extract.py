import re

def extract_structured_signals(parsed_sections: dict) -> dict:
    """
    Extract structured signals from parsed meeting sections.
    Looks for signals in 'Synthesized Signals (Authoritative)' or falls back to individual sections.
    """
    
    # Try to extract from the Synthesized Signals section first
    synthesized = parsed_sections.get("Synthesized Signals (Authoritative)") or parsed_sections.get("Synthesized Signals", "")
    
    if synthesized:
        # Parse the subsections within Synthesized Signals
        signals = extract_from_synthesized_block(synthesized)
    else:
        # Fall back to individual sections
        signals = {
            "decisions": [],
            "action_items": [],
            "blockers": [],
            "risks": [],
            "key_signals": [],
            "ideas": [],
            "context": "",
            "notes": "",
        }
    
    # Also check standalone sections and merge
    def lines(section):
        return [
            l.strip("-• ").strip()
            for l in parsed_sections.get(section, "").splitlines()
            if l.strip() 
            and not l.strip().startswith("<aside") 
            and not l.strip().endswith("</aside>")
            and not l.strip().startswith("###")
            and not l.strip().startswith("**")
            and l.strip() not in ["🚦", "🧩", "✨", "📝", "🟩", "🟪"]
        ]
    
    # Merge with standalone sections if they exist
    if parsed_sections.get("Context"):
        signals["context"] = parsed_sections.get("Context", "")
    
    if parsed_sections.get("Notes") or parsed_sections.get("Notes (raw)"):
        signals["notes"] = parsed_sections.get("Notes") or parsed_sections.get("Notes (raw)", "")
    
    if parsed_sections.get("Key Signal") or parsed_sections.get("Key Signal (Problem)"):
        key_signal_text = parsed_sections.get("Key Signal") or parsed_sections.get("Key Signal (Problem)", "")
        signals["key_signals"] = [key_signal_text] if key_signal_text and not signals["key_signals"] else signals["key_signals"]
    
    # Check for standalone Risks section
    if parsed_sections.get("Risks / Open Questions"):
        risk_text = parsed_sections.get("Risks / Open Questions", "")
        risk_lines = [
            l.strip("-• ").strip()
            for l in risk_text.splitlines()
            if l.strip() 
            and not l.strip().startswith("<aside") 
            and not l.strip().endswith("</aside>")
            and not l.strip().startswith("###")
            and not l.strip().startswith("**")
            and not l.strip().startswith("!")
            and l.strip() not in ["🚦", "🧩", "✨", "📝", "🟩", "🟪"]
        ]
        if risk_lines and not signals["risks"]:
            signals["risks"] = risk_lines
    
    # Check for standalone Ideas section
    if parsed_sections.get("Ideas"):
        ideas = lines("Ideas")
        if ideas and not signals["ideas"]:
            signals["ideas"] = ideas
    
    # Check for standalone Commitments
    commitments_section = parsed_sections.get("Commitments", "")
    if commitments_section:
        commitment_lines = lines("Commitments")
        # Add to action items if not already present
        signals["action_items"].extend([c for c in commitment_lines if c not in signals["action_items"]])

    return signals


def extract_from_synthesized_block(text: str) -> dict:
    """
    Extract signals from a Synthesized Signals block that contains subsections.
    Format example:
    Decision:
    - item 1
    - item 2
    
    Action items:
    item 3
    item 4
    """
    result = {
        "decisions": [],
        "action_items": [],
        "blockers": [],
        "risks": [],
        "key_signals": [],
        "ideas": [],
        "context": "",
        "notes": "",
    }
    
    current_section = None
    lines_list = text.splitlines()
    
    for line in lines_list:
        stripped = line.strip()
        
        # Skip empty lines, aside tags, and emoji markers
        if not stripped or stripped.startswith("<aside") or stripped.endswith("</aside>") or stripped in ["🚦", "🧩", "✨", "📝", "🟩", "🟪"]:
            continue
        
        # Check for section headers (case-insensitive check for flexibility)
        if stripped.startswith("Decision:"):
            current_section = "decisions"
            continue
        elif stripped.startswith("Action items:") or stripped.startswith("Action Items:"):
            current_section = "action_items"
            continue
        elif stripped.startswith("Blocked:"):
            current_section = "blockers"
            continue
        elif stripped.startswith("Risks") or stripped.startswith("**Risks"):
            current_section = "risks"
            continue
        elif stripped.startswith("Ideas:"):
            current_section = "ideas"
            continue
        elif stripped.startswith("Key Signal"):
            current_section = "key_signals"
            continue
        
        # Add line content to current section
        if current_section and stripped:
            # Remove leading dash/bullet if present, otherwise use line as-is
            item = stripped.lstrip("-• ").strip()
            if item and item not in result[current_section]:
                result[current_section].append(item)
    
    return result
