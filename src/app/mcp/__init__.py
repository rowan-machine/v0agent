"""
MCP (Model Context Protocol) Module

This module provides tools for MCP command parsing, inference, and execution.
"""

from .commands import (
    MCP_COMMANDS,
    MCP_INFERENCE_PATTERNS,
    get_all_commands,
    get_all_inference_patterns,
    get_command_info,
    get_subcommand_info,
)

from .command_parser import (
    parse_mcp_command,
    infer_mcp_command,
    get_command_help,
    format_command_suggestion,
)

__all__ = [
    # Commands
    "MCP_COMMANDS",
    "MCP_INFERENCE_PATTERNS",
    "get_all_commands",
    "get_all_inference_patterns",
    "get_command_info",
    "get_subcommand_info",
    # Parser
    "parse_mcp_command",
    "infer_mcp_command",
    "get_command_help",
    "format_command_suggestion",
]
