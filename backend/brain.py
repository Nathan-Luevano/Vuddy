"""
Vuddy Backend — Conversation Orchestrator (Brain).
Processes messages through the full pipeline:
state -> LLM -> tools -> text -> TTS -> audio.
"""

import json

from backend.constants import ASSISTANT_STATES, WS_TYPES_OUT
from backend import elevenlabs_tts, profile_store, school_config, tools as tools_module
from backend.tools import TOOL_DEFINITIONS, MAX_TOOL_CALLS_PER_TURN

# Chat history: keep last 10 messages in memory
_chat_history: list[dict] = []
MAX_HISTORY = 10
MAX_RESPONSE_CHARS = 480

# Base system prompt — school-specific context is injected dynamically
SYSTEM_PROMPT_BASE = """You are Vuddy, a friendly and helpful AI campus desk buddy for college students. You help with:
- Finding campus events and activities
- Managing study sessions (Pomodoro-style timers)
- Calendar management and reminders
- Personalized event recommendations based on interests
- Playing music via Spotify links

Personality:
- Warm, upbeat, and encouraging
- Speak naturally like a helpful friend, not a robot
- Keep responses concise for voice output (2-3 sentences max)
- Use casual language appropriate for college students
- Be proactive in suggesting relevant events or activities

When using tools, always explain what you found in a natural, conversational way.
Never mention internal tool names to the user."""


def _get_system_prompt() -> str:
    """Build the full system prompt with school-specific context."""
    school_context = school_config.get_school_prompt_context()
    return f"{SYSTEM_PROMPT_BASE}\n\nSchool Context:\n{school_context}"


async def process_message(text: str, ws, llm_provider, hardware) -> None:
    """
    Main conversation pipeline. Steps 1-11 from the spec.
    """
    try:
        # Step 1: Send thinking state via WS
        await _send_ws(ws, {"type": "assistant_state", "state": "thinking"})

        # Step 2: Set hardware LED to thinking
        await hardware.set_led_state("thinking")

        # Step 3: Retrieve user profile context
        profile_context = profile_store.get_profile_context()

        # Step 4: Build messages array
        messages = _build_messages(text, profile_context)

        # Step 5: Call LLM with tools
        response = await llm_provider.chat(messages, tools=TOOL_DEFINITIONS)

        # Step 6: Handle tool calls if returned
        tool_results_summary = []
        tool_calls = response.get("tool_calls", [])

        if tool_calls:
            # Limit to MAX_TOOL_CALLS_PER_TURN
            tool_calls = tool_calls[:MAX_TOOL_CALLS_PER_TURN]

            for tool_call in tool_calls:
                tool_name = tool_call.get("function", {}).get("name", "")
                raw_args = tool_call.get("function", {}).get("arguments", {})

                # Parse arguments if they're a string
                if isinstance(raw_args, str):
                    try:
                        tool_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        tool_args = {}
                else:
                    tool_args = raw_args

                # Step 6a: Send tool_status calling
                await _send_ws(ws, {
                    "type": "tool_status",
                    "tool": tool_name,
                    "status": "calling",
                })

                # Step 6b: Execute tool
                tool_result = await tools_module.execute_tool(tool_name, tool_args)

                # Step 6c: Send tool_status done
                status = "done" if tool_result.get("ok") else "error"
                await _send_ws(ws, {
                    "type": "tool_status",
                    "tool": tool_name,
                    "status": status,
                })

                # Step 6d: Append tool result to messages
                messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [tool_call],
                })
                messages.append({
                    "role": "tool",
                    "content": json.dumps(tool_result),
                })

                # Build summary for frontend
                tool_results_summary.append({
                    "tool": tool_name,
                    "summary": _summarize_tool_result(tool_name, tool_result),
                })

            # Step 6e: Call LLM again without tools for final response
            response = await llm_provider.chat(messages, tools=None)

        # Extract response text
        response_text = response.get("content", "")
        if not response_text:
            response_text = "I'm sorry, I couldn't generate a response. Could you try asking again?"
        elif len(response_text) > MAX_RESPONSE_CHARS:
            response_text = response_text[:MAX_RESPONSE_CHARS].rstrip()
            if not response_text.endswith(('.', '!', '?')):
                response_text += "..."

        # Step 7: Send assistant_text via WS
        text_msg = {"type": "assistant_text", "text": response_text}
        if tool_results_summary:
            text_msg["tool_results"] = tool_results_summary
        await _send_ws(ws, text_msg)

        # Update chat history
        _chat_history.append({"role": "user", "content": text})
        _chat_history.append({"role": "assistant", "content": response_text})
        # Trim history to last MAX_HISTORY messages
        while len(_chat_history) > MAX_HISTORY:
            _chat_history.pop(0)

        # Step 8: Generate TTS audio
        audio_path = await elevenlabs_tts.synthesize(response_text)

        if audio_path:
            # Step 9: Send assistant_audio_ready via WS
            # Convert file path to API URL
            filename = audio_path.split("/")[-1]
            audio_url = f"/api/audio/tts/{filename}"
            await _send_ws(ws, {
                "type": "assistant_audio_ready",
                "audio_url": audio_url,
                "format": "mp3",
            })

        # Step 10: Send speaking state
        await _send_ws(ws, {"type": "assistant_state", "state": "speaking"})

        # Step 11: Set hardware LED to speaking
        await hardware.set_led_state("speaking")

    except Exception as e:
        print(f"[BRAIN] Error processing message: {e}")
        await _send_ws(ws, {
            "type": "error",
            "message": str(e),
            "recoverable": True,
        })
        await _send_ws(ws, {"type": "assistant_state", "state": "idle"})
        await hardware.set_led_state("idle")


def _build_messages(user_text: str, profile_context: str) -> list[dict]:
    """Build the messages array for the LLM call."""
    system_content = _get_system_prompt()
    if profile_context:
        system_content += f"\n\nUser Profile:\n{profile_context}"

    messages = [{"role": "system", "content": system_content}]

    # Add chat history
    for msg in _chat_history:
        messages.append(msg)

    # Add current user message
    messages.append({"role": "user", "content": user_text})

    return messages


def _summarize_tool_result(tool_name: str, result: dict) -> str:
    """Generate a brief summary of a tool result for the frontend."""
    if not result.get("ok"):
        return f"{tool_name} failed: {result.get('error', 'unknown error')}"

    if tool_name == "get_events":
        count = len(result.get("events", []))
        return f"Found {count} event{'s' if count != 1 else ''}"

    if tool_name == "get_recommendations":
        count = len(result.get("events", []))
        return f"Found {count} recommendation{'s' if count != 1 else ''}"

    if tool_name == "get_calendar_summary":
        count = len(result.get("events", []))
        return f"Found {count} upcoming item{'s' if count != 1 else ''}"

    if tool_name == "add_calendar_item":
        return f"Added to calendar (ID: {result.get('id', '?')})"

    if tool_name == "start_study_session":
        return f"Started study session until {result.get('end_time', '?')}"

    if tool_name == "stop_study_session":
        return f"Session ended after {result.get('elapsed_min', '?')} minutes"

    if tool_name == "spotify_search_link":
        return f"Spotify link generated"

    return "Done"


async def _send_ws(ws, data: dict) -> None:
    """Send a JSON message over WebSocket, with error handling."""
    try:
        await ws.send_json(data)
    except Exception as e:
        print(f"[BRAIN] Failed to send WS message: {e}")


def clear_history() -> None:
    """Clear chat history (e.g., on new connection)."""
    global _chat_history
    _chat_history = []
