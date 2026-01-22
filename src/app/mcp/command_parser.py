"""
MCP Command Parser

Parses MCP short notation commands from user messages and infers commands
from natural language context.

Extracted from agents/arjuna.py for better separation of concerns.
"""

import re
from typing import Any, Dict, List, Optional

from .commands import MCP_COMMANDS, MCP_INFERENCE_PATTERNS


# =============================================================================
# COMMAND PARSING
# =============================================================================


def parse_mcp_command(message: str) -> Optional[Dict[str, Any]]:
    """
    Parse MCP short notation command from user message.
    
    Formats supported:
    - /command subcommand [args]
    - @agent message (shorthand for /agent ask)
    - Direct command aliases
    
    Args:
        message: User's message (natural language or /command)
    
    Returns:
        Dict with command, subcommand, args if valid command
        None if not a command (natural language)
    """
    message = message.strip()
    
    # Not a command if doesn't start with / or @
    if not message.startswith('/') and not message.startswith('@'):
        return None
    
    # Handle @agent shorthand
    if message.startswith('@'):
        parts = message[1:].split(maxsplit=1)
        if len(parts) >= 1:
            agent_name = parts[0].lower()
            query = parts[1] if len(parts) > 1 else ""
            return {
                "command": "agent",
                "subcommand": "ask",
                "args": {"target_agent": agent_name, "query_text": query},
                "raw": message,
            }
        return None
    
    # Handle /command subcommand args
    parts = message[1:].split()
    if not parts:
        return None
    
    command = parts[0].lower()
    subcommand = parts[1].lower() if len(parts) > 1 else None
    arg_parts = parts[2:] if len(parts) > 2 else []
    
    # Resolve command alias
    resolved_command = None
    for cmd_name, cmd_info in MCP_COMMANDS.items():
        if command == cmd_name or command in cmd_info.get("aliases", []):
            resolved_command = cmd_name
            break
    
    if not resolved_command:
        return None
    
    cmd_info = MCP_COMMANDS[resolved_command]
    
    # If no subcommand, check if it's a help request
    if not subcommand:
        return {
            "command": resolved_command,
            "subcommand": "help",
            "args": {},
            "raw": message,
        }
    
    # Resolve subcommand alias
    resolved_subcommand = None
    for sub_name, sub_info in cmd_info.get("subcommands", {}).items():
        if subcommand == sub_name or subcommand in sub_info.get("aliases", []):
            resolved_subcommand = sub_name
            break
    
    if not resolved_subcommand:
        # Treat as natural language with command context
        return {
            "command": resolved_command,
            "subcommand": "natural",
            "args": {"query": " ".join([subcommand] + arg_parts)},
            "raw": message,
        }
    
    # Parse args based on subcommand spec
    sub_info = cmd_info["subcommands"][resolved_subcommand]
    parsed_args = _parse_command_args(arg_parts, sub_info.get("args", []))
    
    return {
        "command": resolved_command,
        "subcommand": resolved_subcommand,
        "args": parsed_args,
        "raw": message,
        "intent": sub_info.get("intent"),
    }


def _parse_command_args(arg_parts: List[str], expected_args: List[str]) -> Dict[str, Any]:
    """
    Parse command arguments into a dict.
    
    Supports:
    - Positional args: /cmd sub arg1 arg2
    - Named args: /cmd sub --name value
    - Flags: /cmd sub --flag
    
    Args:
        arg_parts: List of argument tokens
        expected_args: List of expected positional argument names
    
    Returns:
        Dict mapping argument names to values
    """
    args = {}
    positional_idx = 0
    i = 0
    
    while i < len(arg_parts):
        part = arg_parts[i]
        
        if part.startswith('--'):
            # Named argument or flag
            key = part[2:].replace('-', '_')
            if i + 1 < len(arg_parts) and not arg_parts[i + 1].startswith('--'):
                args[key] = arg_parts[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            # Positional argument
            if positional_idx < len(expected_args):
                args[expected_args[positional_idx]] = part
                positional_idx += 1
            else:
                # Extra positional args go into 'extra'
                if 'extra' not in args:
                    args['extra'] = []
                args['extra'].append(part)
            i += 1
    
    return args


# =============================================================================
# COMMAND INFERENCE FROM NATURAL LANGUAGE
# =============================================================================


def infer_mcp_command(
    message: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Infer MCP command from natural language context.
    
    This function detects when a user implies an MCP command without using
    explicit notation like /command or @agent.
    
    Args:
        message: User's natural language message
        context: Optional context (current page, recent commands, conversation)
    
    Returns:
        Dict with inferred command, subcommand, args, confidence if detected
        None if no command pattern matches
    """
    message_lower = message.lower().strip()
    context = context or {}
    
    # Skip if it's already an explicit command
    if message_lower.startswith('/') or message_lower.startswith('@'):
        return None
    
    best_match = None
    best_confidence = 0.0
    
    for command, subcommands in MCP_INFERENCE_PATTERNS.items():
        for subcommand, patterns_info in subcommands.items():
            confidence = 0.0
            matched_pattern = None
            extracted_args = {}
            
            # Check regex patterns
            for pattern in patterns_info.get("patterns", []):
                match = re.search(pattern, message_lower)
                if match:
                    confidence = max(confidence, 0.8)  # Pattern match is high confidence
                    matched_pattern = pattern
                    # Try to extract args from named groups
                    if match.lastgroup:
                        extracted_args.update(match.groupdict())
                    break
            
            # Check keyword matches
            for keyword in patterns_info.get("keywords", []):
                if keyword.lower() in message_lower:
                    confidence = max(confidence, 0.6)  # Keyword match is medium confidence
                    if not matched_pattern:
                        matched_pattern = f"keyword:{keyword}"
            
            # Boost confidence based on context
            if context.get("current_page"):
                # Boost if command matches current page context
                page_cmd_map = {
                    "tickets": "arjuna",
                    "meetings": "meeting",
                    "signals": "meeting",
                    "career": "career",
                    "dikw": "dikw",
                }
                if page_cmd_map.get(context.get("current_page")) == command:
                    confidence *= 1.2
            
            if context.get("recent_command") == command:
                # Slightly boost if user recently used this command
                confidence *= 1.1
            
            # Cap confidence at 1.0
            confidence = min(confidence, 1.0)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = {
                    "command": command,
                    "subcommand": subcommand,
                    "args": extracted_args,
                    "confidence": confidence,
                    "matched_pattern": matched_pattern,
                    "raw": message,
                    "inferred": True,
                    "intent": MCP_COMMANDS.get(command, {}).get("subcommands", {}).get(subcommand, {}).get("intent"),
                }
    
    # Only return if confidence meets threshold
    if best_match and best_confidence >= 0.5:
        return best_match
    
    return None


# =============================================================================
# HELP TEXT GENERATION
# =============================================================================


def get_command_help(command: str = None, subcommand: str = None) -> str:
    """
    Get help text for commands.
    
    Args:
        command: Specific command to get help for (None = all commands)
        subcommand: Specific subcommand to get help for
    
    Returns:
        Formatted help text in markdown
    """
    if command and command in MCP_COMMANDS:
        cmd_info = MCP_COMMANDS[command]
        
        if subcommand and subcommand in cmd_info.get("subcommands", {}):
            # Help for specific subcommand
            sub_info = cmd_info["subcommands"][subcommand]
            lines = [
                f"**/{command} {subcommand}** - {sub_info['description']}",
                "",
                f"**Usage:** `{sub_info['usage']}`",
            ]
            if sub_info.get("aliases"):
                lines.append(f"**Aliases:** {', '.join(sub_info['aliases'])}")
            return "\n".join(lines)
        
        # Help for command with all subcommands
        lines = [
            f"**/{command}** - {cmd_info['description']}",
            "",
            f"**Aliases:** {', '.join(cmd_info.get('aliases', []))}",
            "",
            "**Subcommands:**",
        ]
        for sub_name, sub_info in cmd_info.get("subcommands", {}).items():
            aliases = ", ".join(sub_info.get("aliases", []))
            lines.append(f"  • **{sub_name}** ({aliases}): {sub_info['description']}")
        return "\n".join(lines)
    
    # Help for all commands
    lines = [
        "**SignalFlow MCP Commands**",
        "",
        "Use `/command subcommand [args]` or `@agent message` for quick actions.",
        "",
    ]
    for cmd_name, cmd_info in MCP_COMMANDS.items():
        aliases = ", ".join(cmd_info.get("aliases", []))
        lines.append(f"• **/{cmd_name}** ({aliases}): {cmd_info['description']}")
    
    lines.extend([
        "",
        "Type `/command help` for details on a specific command.",
    ])
    return "\n".join(lines)


def format_command_suggestion(command: str, subcommand: str) -> str:
    """
    Format a command suggestion for display.
    
    Args:
        command: The command name
        subcommand: The subcommand name
    
    Returns:
        Formatted suggestion string
    """
    cmd_info = MCP_COMMANDS.get(command, {})
    sub_info = cmd_info.get("subcommands", {}).get(subcommand, {})
    
    if sub_info:
        return f"`/{command} {subcommand}` - {sub_info.get('description', '')}"
    return f"`/{command} {subcommand}`"
