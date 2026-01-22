"""
MCP Short Notation Commands

User-facing command shortcuts for human-in-the-loop chat interactions.
Format: /command subcommand [args] or @agent command

Extracted from agents/arjuna.py for better separation of concerns.
"""

from typing import Any, Dict, Optional


# =============================================================================
# MCP COMMAND DEFINITIONS
# =============================================================================

MCP_COMMANDS = {
    # Arjuna (Assistant) Commands
    "arjuna": {
        "description": "Smart assistant for focus & priority intelligence",
        "aliases": ["aj", "a", "assistant"],
        "subcommands": {
            "focus": {
                "description": "Get prioritized work recommendations",
                "usage": "/arjuna focus",
                "aliases": ["f", "what-next", "prioritize"],
                "intent": "focus_recommendations",
            },
            "ticket": {
                "description": "Create a new ticket",
                "usage": "/arjuna ticket <title> [--priority high|medium|low]",
                "aliases": ["t", "create", "add"],
                "intent": "create_ticket",
                "args": ["title", "priority", "description"],
            },
            "update": {
                "description": "Update a ticket status or priority",
                "usage": "/arjuna update <ticket_id> [--status done|blocked|in_progress] [--priority high]",
                "aliases": ["u", "set"],
                "intent": "update_ticket",
                "args": ["ticket_id", "status", "priority"],
            },
            "list": {
                "description": "List tickets with optional status filter",
                "usage": "/arjuna list [--status todo|in_progress|blocked|done]",
                "aliases": ["ls", "tickets"],
                "intent": "list_tickets",
                "args": ["status"],
            },
            "standup": {
                "description": "Log a standup update",
                "usage": "/arjuna standup <yesterday> | <today> | <blockers>",
                "aliases": ["su", "daily"],
                "intent": "create_standup",
                "args": ["yesterday", "today_plan", "blockers"],
            },
            "waiting": {
                "description": "Add a waiting-for accountability item",
                "usage": "/arjuna waiting <description> --from <person>",
                "aliases": ["w", "wf", "accountability"],
                "intent": "create_accountability",
                "args": ["description", "responsible_party"],
            },
            "model": {
                "description": "Change the AI model",
                "usage": "/arjuna model <model_name>",
                "aliases": ["m", "llm"],
                "intent": "change_model",
                "args": ["model"],
            },
            "sprint": {
                "description": "Update sprint settings",
                "usage": "/arjuna sprint [--name <name>] [--goal <goal>]",
                "aliases": ["sp"],
                "intent": "update_sprint",
                "args": ["sprint_name", "sprint_goal"],
            },
            "go": {
                "description": "Navigate to a page",
                "usage": "/arjuna go <page>",
                "aliases": ["nav", "open", "show"],
                "intent": "navigate",
                "args": ["target_page"],
            },
            "search": {
                "description": "Search meetings",
                "usage": "/arjuna search <query>",
                "aliases": ["s", "find"],
                "intent": "search_meetings",
                "args": ["query"],
            },
            "help": {
                "description": "Show available commands",
                "usage": "/arjuna help [command]",
                "aliases": ["h", "?"],
                "intent": "show_help",
            },
        },
    },
    # Query Commands (for data queries)
    "query": {
        "description": "Query data across all entities",
        "aliases": ["q", "data"],
        "subcommands": {
            "list": {
                "description": "List entities of a type",
                "usage": "/query list <entity_type> [--limit N]",
                "aliases": ["ls"],
                "args": ["entity_type", "limit"],
            },
            "search": {
                "description": "Search entities by keyword",
                "usage": "/query search <entity_type> <term>",
                "aliases": ["s", "find"],
                "args": ["entity_type", "term"],
            },
            "filter": {
                "description": "Filter entities by criteria",
                "usage": "/query filter <entity_type> --field value",
                "aliases": ["f"],
                "args": ["entity_type", "filters"],
            },
        },
    },
    # Semantic Search Commands
    "semantic": {
        "description": "Semantic search and similarity",
        "aliases": ["sem", "embed"],
        "subcommands": {
            "search": {
                "description": "Search by semantic similarity",
                "usage": "/semantic search <query> [--types meetings,signals]",
                "aliases": ["s"],
                "args": ["query", "entity_types", "top_k"],
            },
            "similar": {
                "description": "Find similar items",
                "usage": "/semantic similar <entity_type> <id>",
                "aliases": ["sim"],
                "args": ["entity_type", "entity_id"],
            },
            "cluster": {
                "description": "Cluster similar items",
                "usage": "/semantic cluster <entity_type> [--n 5]",
                "aliases": ["c"],
                "args": ["entity_type", "num_clusters"],
            },
        },
    },
    # Agent Communication Commands
    "agent": {
        "description": "Communicate with other agents",
        "aliases": ["@"],
        "subcommands": {
            "ask": {
                "description": "Ask another agent a question",
                "usage": "/agent ask <agent_name> <question>",
                "aliases": ["a"],
                "args": ["target_agent", "query_text"],
            },
            "status": {
                "description": "Get agent status",
                "usage": "/agent status [agent_name]",
                "aliases": ["s"],
                "args": ["target_agent"],
            },
            "list": {
                "description": "List all agents",
                "usage": "/agent list",
                "aliases": ["ls"],
            },
        },
    },
    # Career Coach Commands
    "career": {
        "description": "Career development assistance",
        "aliases": ["cc", "coach"],
        "subcommands": {
            "analyze": {
                "description": "Analyze career progress",
                "usage": "/career analyze",
                "aliases": ["a"],
            },
            "feedback": {
                "description": "Get feedback on standup",
                "usage": "/career feedback <standup_text>",
                "aliases": ["fb"],
                "args": ["standup_text"],
            },
            "goals": {
                "description": "Review career goals",
                "usage": "/career goals",
                "aliases": ["g"],
            },
            "skills": {
                "description": "Assess skills and gaps",
                "usage": "/career skills",
                "aliases": ["sk"],
            },
        },
    },
    # Meeting Analyzer Commands
    "meeting": {
        "description": "Meeting analysis and signal extraction",
        "aliases": ["mtg", "meetings"],
        "subcommands": {
            "analyze": {
                "description": "Analyze meeting notes",
                "usage": "/meeting analyze <notes>",
                "aliases": ["a"],
                "args": ["notes"],
            },
            "signals": {
                "description": "Extract signals from meeting",
                "usage": "/meeting signals <meeting_id>",
                "aliases": ["sig", "s"],
                "args": ["meeting_id"],
            },
            "recent": {
                "description": "Show recent meetings",
                "usage": "/meeting recent [--limit N]",
                "aliases": ["r", "list"],
                "args": ["limit"],
            },
        },
    },
    # DIKW Synthesizer Commands
    "dikw": {
        "description": "Knowledge synthesis and promotion",
        "aliases": ["k", "knowledge"],
        "subcommands": {
            "promote": {
                "description": "Promote signal up the DIKW hierarchy",
                "usage": "/dikw promote <signal_id> [--to info|knowledge|wisdom]",
                "aliases": ["p"],
                "args": ["signal_id", "target_level"],
            },
            "synthesize": {
                "description": "Synthesize related signals",
                "usage": "/dikw synthesize <signal_ids>",
                "aliases": ["syn", "s"],
                "args": ["signal_ids"],
            },
            "mindmap": {
                "description": "Generate concept mindmap",
                "usage": "/dikw mindmap [--tags tag1,tag2]",
                "aliases": ["mm", "map"],
                "args": ["tags"],
            },
        },
    },
}


# =============================================================================
# CONTEXT-BASED MCP COMMAND INFERENCE PATTERNS
# =============================================================================

MCP_INFERENCE_PATTERNS = {
    # Arjuna Commands Inference
    "arjuna": {
        "focus": {
            "patterns": [
                r"what\s+should\s+i\s+(work|focus)\s+on",
                r"(prioritize|priorities)\s+(my|for)?(tasks|work|today)?",
                r"what('?s|\s+is)?\s+next",
                r"what\s+to\s+do\s+(first|now|next)",
                r"help\s+me\s+(focus|prioritize)",
                r"(most|top)\s+important\s+(task|thing|item)",
                r"where\s+should\s+i\s+start",
            ],
            "keywords": ["focus", "prioritize", "what next", "work on", "start with"],
        },
        "ticket": {
            "patterns": [
                r"(create|add|make|new)\s+(a\s+)?(ticket|task|todo|item)",
                r"i\s+need\s+to\s+(track|add)\s+(a\s+)?(task|ticket)",
                r"add\s+this\s+to\s+my\s+(list|tickets|tasks)",
                r"(track|log)\s+(this|that)\s+as\s+a\s+ticket",
            ],
            "keywords": ["create ticket", "add task", "new ticket", "make ticket"],
            "extract": ["title", "priority", "description"],
        },
        "standup": {
            "patterns": [
                r"(log|record|add)\s+(my\s+)?standup",
                r"daily\s+(standup|update|status)",
                r"what\s+i\s+(did|worked\s+on)\s+yesterday",
                r"my\s+(standup|update)\s+(is|for\s+today)",
            ],
            "keywords": ["standup", "daily update", "yesterday", "today plan"],
        },
        "waiting": {
            "patterns": [
                r"(waiting|wait)\s+(for|on)\s+\w+",
                r"(need|depends)\s+(something|response|input)\s+from",
                r"blocked\s+(by|on|waiting)",
                r"track\s+(accountability|dependency)",
            ],
            "keywords": ["waiting for", "depends on", "blocked by", "accountability"],
            "extract": ["description", "responsible_party"],
        },
        "model": {
            "patterns": [
                r"(switch|change|use|set)\s+(to\s+)?(model|llm|ai)",
                r"(use|switch\s+to)\s+(gpt|claude|opus|sonnet|haiku)",
            ],
            "keywords": ["change model", "switch model", "use gpt", "use claude"],
        },
        "go": {
            "patterns": [
                r"(go|take|show|open|navigate)\s+(me\s+)?(to\s+)?(the\s+)?(\w+)\s+(page|screen|section)?",
                r"(show|open)\s+(me\s+)?(the\s+)?(dashboard|tickets|signals|meetings|career|dikw)",
            ],
            "keywords": ["go to", "show me", "open", "navigate to"],
            "extract": ["target_page"],
        },
        "search": {
            "patterns": [
                r"(search|find|look)\s+(for\s+)?(meetings?|in\s+meetings?)",
                r"(find|search)\s+.+\s+in\s+(meetings|signals)",
            ],
            "keywords": ["search meetings", "find in meetings"],
        },
        "help": {
            "patterns": [
                r"(what|which)\s+commands?\s+(are|can)",
                r"(help|commands|options|what\s+can\s+you\s+do)",
                r"(show|list)\s+(me\s+)?(all\s+)?commands?",
            ],
            "keywords": ["help", "commands", "what can you do"],
        },
    },
    # Query Commands Inference
    "query": {
        "list": {
            "patterns": [
                r"(list|show|get)\s+(all\s+)?(my\s+)?(tickets|meetings|signals|documents)",
                r"what\s+(tickets|meetings|signals|documents)\s+(do\s+i\s+have|are\s+there)",
            ],
            "keywords": ["list tickets", "show meetings", "get signals"],
            "extract": ["entity_type", "limit"],
        },
        "search": {
            "patterns": [
                r"(find|search)\s+(tickets|meetings|signals)\s+(with|containing|about)",
            ],
            "keywords": ["find tickets", "search meetings"],
        },
    },
    # Semantic Search Inference
    "semantic": {
        "search": {
            "patterns": [
                r"(semantic|smart|ai)\s+search",
                r"find\s+similar\s+to",
                r"(search|find)\s+(by\s+)?(meaning|concept|related)",
            ],
            "keywords": ["semantic search", "find similar", "related to"],
        },
        "similar": {
            "patterns": [
                r"(find|show|get)\s+similar\s+(items?|tickets?|meetings?|signals?)",
                r"what('?s|\s+is)\s+similar\s+to",
            ],
            "keywords": ["find similar", "what's similar"],
        },
    },
    # Career Coach Inference
    "career": {
        "analyze": {
            "patterns": [
                r"(analyze|review|assess)\s+(my\s+)?career",
                r"how\s+am\s+i\s+doing\s+(professionally|at\s+work)",
                r"career\s+(progress|review|analysis)",
            ],
            "keywords": ["career analysis", "career progress", "how am i doing"],
        },
        "feedback": {
            "patterns": [
                r"(give|get)\s+(me\s+)?feedback\s+on",
                r"feedback\s+(for|on)\s+(my\s+)?(standup|work|progress)",
            ],
            "keywords": ["feedback", "give feedback", "review my"],
        },
        "skills": {
            "patterns": [
                r"(assess|review|check)\s+(my\s+)?skills?",
                r"(skill|skills)\s+(gap|assessment|review)",
                r"what\s+skills\s+(do\s+i\s+need|am\s+i\s+missing)",
            ],
            "keywords": ["skills", "skill gap", "skill assessment"],
        },
    },
    # Meeting Analyzer Inference
    "meeting": {
        "analyze": {
            "patterns": [
                r"(analyze|review|process)\s+(this\s+)?(meeting|notes)",
                r"extract\s+(signals?|insights?)\s+from",
            ],
            "keywords": ["analyze meeting", "process notes", "extract signals"],
        },
        "signals": {
            "patterns": [
                r"(show|get|extract)\s+(the\s+)?signals?\s+(from|for)",
                r"what\s+(signals?|decisions?|actions?)\s+(came|are)\s+from",
            ],
            "keywords": ["meeting signals", "extract signals", "decisions from meeting"],
        },
        "recent": {
            "patterns": [
                r"(show|list|get)\s+(recent|latest|last)\s+meetings?",
                r"(my\s+)?recent\s+meetings?",
            ],
            "keywords": ["recent meetings", "latest meetings", "last meeting"],
        },
    },
    # DIKW Synthesizer Inference
    "dikw": {
        "promote": {
            "patterns": [
                r"promote\s+(this|signal|it)\s+(to|up)",
                r"(move|upgrade)\s+(to\s+)?(knowledge|wisdom|info)",
                r"(make|turn)\s+(this|it)\s+(into\s+)?(knowledge|wisdom)",
            ],
            "keywords": ["promote signal", "upgrade to knowledge", "make wisdom"],
        },
        "synthesize": {
            "patterns": [
                r"(synthesize|combine|merge)\s+(these\s+)?signals?",
                r"(create|build)\s+(a\s+)?(synthesis|summary)\s+from",
            ],
            "keywords": ["synthesize", "combine signals", "merge signals"],
        },
        "mindmap": {
            "patterns": [
                r"(create|generate|show|build)\s+(a\s+)?(concept\s+)?mindmap",
                r"(visualize|map)\s+(the\s+)?(concepts?|knowledge)",
            ],
            "keywords": ["mindmap", "concept map", "visualize concepts"],
        },
    },
}


def get_all_commands() -> Dict[str, Any]:
    """Get all MCP commands."""
    return MCP_COMMANDS


def get_all_inference_patterns() -> Dict[str, Any]:
    """Get all MCP inference patterns."""
    return MCP_INFERENCE_PATTERNS


def get_command_info(command: str) -> Optional[Dict[str, Any]]:
    """Get info for a specific command."""
    return MCP_COMMANDS.get(command)


def get_subcommand_info(command: str, subcommand: str) -> Optional[Dict[str, Any]]:
    """Get info for a specific subcommand."""
    cmd_info = MCP_COMMANDS.get(command, {})
    return cmd_info.get("subcommands", {}).get(subcommand)
