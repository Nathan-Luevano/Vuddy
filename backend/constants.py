"""
Vuddy Backend — Frozen Enum Constants.
Import these everywhere instead of using raw strings.
"""

ASSISTANT_STATES = ["idle", "listening", "thinking", "speaking", "error"]

LED_MODES = ["pulse", "solid", "breathe", "off"]

LLM_PROVIDERS = ["ollama", "patriotai"]

HARDWARE_MODES = ["sim", "arduino"]

TOOL_NAMES = [
    "get_events",
    "get_recommendations",
    "get_calendar_summary",
    "add_calendar_item",
    "start_study_session",
    "stop_study_session",
    "spotify_search_link",
]

WS_TYPES_OUT = [
    "assistant_text",
    "assistant_audio_ready",
    "assistant_state",
    "tool_status",
    "error",
]

WS_TYPES_IN = [
    "start_listening",
    "stop_listening",
    "transcript_final",
    "chat",
    "interrupt",
]
