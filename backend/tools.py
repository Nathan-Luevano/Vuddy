"""
Vuddy Backend — Tool Router.
7 tools as OpenAI-compatible function definitions.
Max 2 tool calls per turn. 1 retry on failure.
"""

import asyncio
import json

from backend.constants import TOOL_NAMES
from backend import events_service, recommender, calendar_service, study_service, spotify_links

# OpenAI-compatible tool definitions for the LLM
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_events",
            "description": "Get campus events happening around a time range",
            "parameters": {
                "type": "object",
                "properties": {
                    "time_range": {
                        "type": "string",
                        "description": "e.g. 'tonight', 'tomorrow', 'this weekend'",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags like 'social', 'academic', 'sports'",
                    },
                },
                "required": ["time_range"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recommendations",
            "description": "Get personalized event recommendations based on user interests",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of recommendations to return",
                        "default": 3,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar_summary",
            "description": "Get upcoming calendar events",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_ahead": {
                        "type": "integer",
                        "description": "How many hours ahead to look",
                        "default": 24,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_calendar_item",
            "description": "Add a reminder or event to the calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "time_iso": {
                        "type": "string",
                        "description": "ISO 8601 datetime",
                    },
                    "notes": {"type": "string"},
                },
                "required": ["title", "time_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "start_study_session",
            "description": "Start a Pomodoro-style study session",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "duration_min": {
                        "type": "integer",
                        "description": "Duration in minutes",
                        "default": 25,
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop_study_session",
            "description": "End an active study session",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                },
                "required": ["session_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_search_link",
            "description": "Generate a Spotify search URL (no OAuth needed)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]

# Timeout per tool (seconds), matching shared/tools.schema.json
TOOL_TIMEOUTS = {
    "get_events": 2,
    "get_recommendations": 3,
    "get_calendar_summary": 2,
    "add_calendar_item": 2,
    "start_study_session": 1,
    "stop_study_session": 1,
    "spotify_search_link": 1,
}

MAX_TOOL_CALLS_PER_TURN = 2
MAX_RETRIES = 1


async def execute_tool(tool_name: str, arguments: dict) -> dict:
    """
    Execute a tool by name with the given arguments.
    Includes timeout and 1 retry on failure.
    """
    if tool_name not in TOOL_NAMES:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    timeout = TOOL_TIMEOUTS.get(tool_name, 2)

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(
                _run_tool(tool_name, arguments),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            if attempt < MAX_RETRIES:
                print(f"[TOOLS] {tool_name} timed out, retrying ({attempt + 1}/{MAX_RETRIES})")
                continue
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"[TOOLS] {tool_name} failed ({e}), retrying ({attempt + 1}/{MAX_RETRIES})")
                continue
            return {"ok": False, "error": str(e)}


async def _run_tool(tool_name: str, arguments: dict) -> dict:
    """Route to the correct tool implementation."""
    if tool_name == "get_events":
        return events_service.get_events(
            time_range=arguments.get("time_range", "today"),
            tags=arguments.get("tags"),
        )

    elif tool_name == "get_recommendations":
        return await recommender.get_recommendations(
            count=arguments.get("count", 3),
        )

    elif tool_name == "get_calendar_summary":
        return calendar_service.get_summary(
            hours_ahead=arguments.get("hours_ahead", 24),
        )

    elif tool_name == "add_calendar_item":
        return calendar_service.add_item(
            title=arguments["title"],
            time_iso=arguments["time_iso"],
            notes=arguments.get("notes", ""),
        )

    elif tool_name == "start_study_session":
        return study_service.start_session(
            topic=arguments["topic"],
            duration_min=arguments.get("duration_min", 25),
        )

    elif tool_name == "stop_study_session":
        return study_service.stop_session(
            session_id=arguments["session_id"],
        )

    elif tool_name == "spotify_search_link":
        return spotify_links.search_link(
            query=arguments["query"],
        )

    return {"ok": False, "error": f"Unknown tool: {tool_name}"}
