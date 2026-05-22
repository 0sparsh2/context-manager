"""OpenAI-compatible tool definitions for the agent loop."""

from __future__ import annotations

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_spans",
            "description": "Search observability spans/traces. Returns large payload; older results may be archived.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query or trace id"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a source file from the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_segment",
            "description": "Recall full content of an archived context segment by id from warm store.",
            "parameters": {
                "type": "object",
                "properties": {
                    "segment_id": {"type": "string", "description": "UUID from [archived segment id=...]"},
                },
                "required": ["segment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_by_keyword",
            "description": "Search archived segments for a keyword and return matching full content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "Substring to find in archived content"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_archived",
            "description": "List archived segment ids and previews from the warm store.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
