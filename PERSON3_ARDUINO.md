# PERSON 3: Integration, Data, QA, and Docs
## Your job: Make sure Person 1 and Person 2 can merge painlessly. Own the glue.
## You own: `shared/`, `scripts/`, `data/`, documentation. You touch nothing else.

**Read `WORKSTREAM_CONTRACTS.md` first. Keep it open at all times.**

---

## YOUR SCOPE

You are the **integration owner**. Your deliverables:

1. **Shared contract schemas** in `shared/` that both frontend and backend reference
2. **Seed dataset** for campus events in `data/events_seed.json`
3. **Smoke test script** in `scripts/smoke_ws_client.py`
4. **Demo checklist** and **track compliance checklist** in this doc
5. **Optional hardware simulator** docs (Arduino is Phase 2, only if time allows)

You do NOT write backend code or frontend code. You write the contracts, test harnesses, and data that make their code interoperate.

---

## YOUR FILES (Create all of these)

```
shared/
  ws_messages.schema.json
  tools.schema.json
  events.schema.json

scripts/
  smoke_ws_client.py

data/
  events_seed.json
  fixtures/
    campus_events.json     # alternate location, same data
    calendar.json          # calendar fixture data
  profile/
    user_profile.json      # default empty profile
```

---

## FILE-BY-FILE BUILD GUIDE

### 1. `shared/ws_messages.schema.json`

Define every WebSocket message type with required fields and examples. This is the single source of truth for message shapes.

**Must include:**

Frontend -> Backend:
- `start_listening`: `{type}` only
- `stop_listening`: `{type}` only
- `transcript_final`: `{type, text}` (text is wake-word-stripped)
- `chat`: `{type, text}` (typed input, no wake word needed)
- `interrupt`: `{type}` only

Backend -> Frontend:
- `assistant_state`: `{type, state, wake_word?, llm_provider?}` (wake_word and llm_provider only on initial connect)
- `assistant_text`: `{type, text, tool_results?}`
- `assistant_audio_ready`: `{type, audio_url, format}` or `{type, audio_b64, format}`
- `tool_status`: `{type, tool, status}`
- `error`: `{type, message, recoverable}`

### 2. `shared/tools.schema.json`

Define every tool's request args and response shape. One entry per tool.

**Must include all 7 tools:**
- `get_events` - args: `{time_range, tags?}` - returns: `{ok, events[]}`
- `get_recommendations` - args: `{count?}` - returns: `{ok, events[], reasons[]}`
- `get_calendar_summary` - args: `{hours_ahead?}` - returns: `{ok, events[]}`
- `add_calendar_item` - args: `{title, time_iso, notes?}` - returns: `{ok, id}`
- `start_study_session` - args: `{topic, duration_min?}` - returns: `{ok, session_id, end_time}`
- `stop_study_session` - args: `{session_id}` - returns: `{ok, elapsed_min}`
- `spotify_search_link` - args: `{query}` - returns: `{ok, url, display_text}`

### 3. `shared/events.schema.json`

Define the event object shape used in seed data.

```json
{
  "event": {
    "id": "string, unique",
    "title": "string, required",
    "start": "string, ISO 8601 datetime",
    "end": "string, ISO 8601 datetime",
    "location": "string",
    "tags": ["string array, lowercase"],
    "description": "string"
  },
  "valid_tags": [
    "social", "academic", "sports", "arts", "music", "food",
    "tech", "wellness", "career", "entertainment", "community",
    "study", "free", "workshop", "hackathon", "outdoor", "fitness",
    "dance", "movies", "opera", "games", "quiet", "networking", "basketball", "culture", "help"
  ]
}
```

### 4. `data/events_seed.json`

Seeded dataset of campus events. **This file makes the demo bulletproof** (no external data dependency).

Requirements:
- At least 15 events
- Span the hackathon weekend (Feb 13-15, 2026)
- Cover diverse categories: social, academic, sports, arts, food, tech, wellness
- Include events at real GMU locations (JC, Fenwick, Innovation Hall, etc.)
- Each event has: id, title, start, end, location, tags, description
- Must conform to `shared/events.schema.json`

(A starter file already exists at `data/fixtures/campus_events.json`. Copy or symlink it.)

### 5. `data/profile/user_profile.json`

Default empty profile:
```json
{
  "interests": [],
  "preferred_times": [],
  "study_habits": {},
  "preferences": {}
}
```

### 6. `scripts/smoke_ws_client.py`

A standalone Python script that tests the backend WebSocket endpoint. No frontend needed.

```python
#!/usr/bin/env python3
"""Smoke test: connect to backend WS and send a test message."""
import asyncio
import json
import websockets

WS_URL = "ws://localhost:8000/ws"

async def smoke_test():
    print(f"Connecting to {WS_URL}...")
    async with websockets.connect(WS_URL) as ws:
        # 1. Expect assistant_state on connect
        msg = json.loads(await ws.recv())
        assert msg["type"] == "assistant_state", f"Expected assistant_state, got {msg['type']}"
        assert msg["state"] == "idle"
        print(f"[PASS] Connected. Provider: {msg.get('llm_provider', 'unknown')}")

        # 2. Send a chat message
        await ws.send(json.dumps({"type": "chat", "text": "what events are happening tonight?"}))
        print("[SENT] chat message")

        # 3. Collect responses (wait up to 20s)
        received_types = []
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=20.0)
                msg = json.loads(raw)
                received_types.append(msg["type"])
                print(f"[RECV] {msg['type']}: {json.dumps(msg)[:120]}")

                if msg["type"] == "assistant_audio_ready":
                    break  # Full cycle complete
                if msg["type"] == "error":
                    print(f"[WARN] Error: {msg['message']}")
                    break
        except asyncio.TimeoutError:
            print("[TIMEOUT] No more messages after 20s")

        # 4. Verify expected message flow
        if "assistant_text" in received_types:
            print("[PASS] Got assistant_text response")
        else:
            print("[FAIL] Missing assistant_text")

        if "assistant_audio_ready" in received_types:
            print("[PASS] Got assistant_audio_ready")
        else:
            print("[WARN] No audio (ElevenLabs may not be configured)")

    print("Smoke test complete.")

if __name__ == "__main__":
    asyncio.run(smoke_test())
```

### 7. `data/fixtures/calendar.json`

Fallback calendar data:
```json
[
  {"title": "CS 310 Lecture", "start": "2026-02-14T09:00:00", "end": "2026-02-14T10:15:00"},
  {"title": "Math 214 Recitation", "start": "2026-02-14T13:00:00", "end": "2026-02-14T13:50:00"},
  {"title": "Team Meeting", "start": "2026-02-14T15:00:00", "end": "2026-02-14T16:00:00"},
  {"title": "Gym", "start": "2026-02-14T17:30:00", "end": "2026-02-14T18:30:00"}
]
```

---

## DEMO CHECKLIST

Run through this before every demo:

- [ ] Backend starts without errors: `cd backend && uvicorn main:app --reload`
- [ ] Frontend starts without errors: `cd frontend && npm run dev`
- [ ] Health check passes: `curl http://localhost:8000/health`
- [ ] Smoke test passes: `python scripts/smoke_ws_client.py`
- [ ] Open Chrome at `http://localhost:5173`
- [ ] Tap "Start Vuddy" (audio unlocks)
- [ ] Click mic, say "Hey Vuddy, what's going on tonight?" (response comes back)
- [ ] Type a message (response comes back)
- [ ] Interrupt works (speak while Vuddy is talking, audio stops)
- [ ] Events tab shows seeded events
- [ ] Study timer starts and counts down
- [ ] Calendar tab shows fixture data
- [ ] Provider badge shows "PatriotAI" (if LLM_PROVIDER=patriotai set)

## TRACK COMPLIANCE CHECKLIST

**Before submitting:**

- [ ] `LLM_PROVIDER=patriotai` is set in `.env`
- [ ] PatriotAI API key is valid and working
- [ ] Provider badge shows "PatriotAI" in the UI
- [ ] Health check shows `"llm_provider":"patriotai"`
- [ ] LinkedIn: followed Cloudforce
- [ ] LinkedIn: posted about project tagging `@goCloudforce`
- [ ] Pitch mentions "Powered by PatriotAI" and "Best Use of PatriotAI" track
- [ ] Study features framed as education/focus coaching
- [ ] Calendar features framed as academic planning

---

## OPTIONAL: HARDWARE APPENDIX (Phase 2, Only If Time Allows)

> This section describes a minimal Arduino build that plugs into the existing
> HardwareInterface. It is NOT required for the demo. The software runs
> perfectly with SimHardware (the default).

### Minimal BOM

| Component | Arduino Pin | Notes |
|-----------|------------|-------|
| NeoPixel Ring (8 LEDs) | D6 | WS2812B, data in |
| Push Button | D2 | Internal pullup, active LOW |

That is the entire BOM. No servos, no sensors, no movement.

### How It Plugs In

1. Set `HARDWARE_MODE=arduino` in `.env`
2. Set `SERIAL_PORT=/dev/ttyUSB0` (or whatever port)
3. Backend creates `ArduinoHardware` instead of `SimHardware`
4. Arduino receives `set_status` commands -> maps to LED patterns:
   - `idle` -> dim blue solid
   - `listening` -> blue pulse
   - `thinking` -> teal breathe
   - `speaking` -> bright blue solid
   - `error` -> red solid
5. Button press -> backend receives `button_press` event -> can trigger `start_listening`

### Arduino Sketch

Same as documented in the HardwareInterface contract in `WORKSTREAM_CONTRACTS.md`.
The sketch is simple: read serial JSON, set LEDs, send button events.
Upload `arduino/vuddy/vuddy.ino` and it conforms to the interface.

### Libraries
```
Adafruit_NeoPixel.h
ArduinoJson.h (v7)
```

### Testing Without Backend
```json
{"t":"cmd","id":"test1","action":"set_status","state":"listening"}
```
Open Serial Monitor at 115200, paste the above, LEDs should pulse blue.

---

## CRITICAL REMINDERS

1. **Schemas are the source of truth.** If Person 1 or Person 2 disagree on a format, the schema wins.
2. **Smoke test must pass before any merge.** Run `scripts/smoke_ws_client.py` after every backend change.
3. **Seed data must always be present.** The demo path must never depend on external services.
4. **Hardware is optional.** Never block on Arduino. SimHardware is the default and the demo works with it.
5. **Track compliance is YOUR checklist.** Make sure LLM_PROVIDER is set to patriotai before judging.
