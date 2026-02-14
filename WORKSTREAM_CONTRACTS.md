# VUDDY CAMPUS DESK BUDDY - INTEGRATION CONTRACTS
## Read This FIRST. This Is What Keeps All 3 Workstreams Connected.

Every message, every file path, every port number is defined here. If you're unsure about a format, **check this file, not your gut.**

---

## TEAM ROLES

| Person | Role | Owns | Touches Nothing Else |
|--------|------|------|---------------------|
| **Person 1** | Backend orchestrator | `backend/` | Tools, LLM provider abstraction (Ollama now, PatriotAI later), ElevenLabs TTS, HardwareInterface |
| **Person 2** | Frontend kiosk UI | `frontend/` | Push-to-talk, transcript display, audio playback, interrupt, provider badge |
| **Person 3** | Integration + Data + QA | `shared/`, `scripts/`, `data/`, docs | Shared schemas, seed dataset, smoke tests, integration docs, optional hardware simulator |

---

## NETWORK TOPOLOGY

```
+--------------------------+
|  PERSON 2: FRONTEND      |
|  (Voice Device UI)       |   HTTP + WS
|  Mic Capture + Speaker   | <------------------->  +----------------------+
|  Wake Word Gating        |   Port 8000            |  PERSON 1: BACKEND   |
|  Port 5173 (dev)         |                        |  (Orchestrator)      |
+--------------------------+                        |  FastAPI + WebSocket |
                                                    |  Port 8000           |
              +------- Person 3 maintains --------->|                      |
              |  shared/ schemas                    |  LLM Provider:       |
              |  scripts/ smoke tests               |    Ollama (default)  |
              |  data/ seed events                  |    PatriotAI (swap)  |
              |                                     |  ElevenLabs (TTS)    |
              |                                     |  HardwareInterface   |
              |  Optional (Phase 2):                |    (SimHardware)     |
+-------------+-------------+                      |                      |
|  HARDWARE (if built)      |   USB Serial          |                      |
|  Arduino LED + Button     | <------------------->  |                      |
|  Conforms to              |   115200 baud         +----------------------+
|  HardwareInterface        |   JSON lines
+---------------------------+
```

---

## CONTRACT 1: Frontend <-> Backend (WebSocket)

**URL:** `ws://localhost:8000/ws`
**Format:** JSON objects
**Every message has a `type` field as discriminator**
**Schemas live in:** `shared/ws_messages.schema.json`

### On Connect (Backend sends immediately)

Backend sends one message on new WS connection:
```json
{"type":"assistant_state","state":"idle","wake_word":"hey vuddy","llm_provider":"ollama"}
```

Frontend uses `llm_provider` to display the provider badge.

### Frontend -> Backend Messages

#### `start_listening` - User taps "Start" button
```json
{"type":"start_listening"}
```

#### `transcript_final` - Wake-word-gated utterance ready
```json
{"type":"transcript_final","text":"what's going on around campus tonight?"}
```
*Frontend strips the wake word prefix before sending. Only sent if transcript begins with "hey vuddy" or "vuddy".*

#### `chat` - Typed input (fallback, always available)
```json
{"type":"chat","text":"What's on my calendar tomorrow?"}
```

#### `interrupt` - User speaks or taps while assistant is speaking
```json
{"type":"interrupt"}
```
*Send BEFORE the new `transcript_final` or `chat` message. Always send both in sequence. Backend cancels in-flight LLM request and stops audio generation.*

#### `stop_listening` - User taps "Stop" (optional)
```json
{"type":"stop_listening"}
```

### Backend -> Frontend Messages

#### `assistant_text` - LLM response text
```json
{
  "type": "assistant_text",
  "text": "There's a game night at the JC at 7 PM and a study group in Fenwick at 8!",
  "tool_results": [{"tool": "get_events", "summary": "Found 3 events tonight"}]
}
```

#### `assistant_audio_ready` - ElevenLabs TTS audio available
```json
{
  "type": "assistant_audio_ready",
  "audio_url": "/api/audio/tts/a1b2c3d4.mp3",
  "format": "mp3"
}
```
*May also use `"audio_b64"` field with base64-encoded audio for WebSocket-only delivery.*

#### `assistant_state` - State change notification
```json
{"type":"assistant_state","state":"thinking"}
```
State values: `"idle"`, `"listening"`, `"thinking"`, `"speaking"`, `"error"`

#### `tool_status` - Tool execution progress
```json
{"type":"tool_status","tool":"get_events","status":"calling"}
```
Status values: `"calling"`, `"done"`, `"error"`

#### `error` - Something went wrong
```json
{"type":"error","message":"LLM timeout","recoverable":true}
```

---

## CONTRACT 2: Frontend <-> Backend (REST API)

**Base URL:** `http://localhost:8000`

| Method | Path | Response | Purpose |
|--------|------|----------|---------|
| GET | `/health` | `{"ok":true,"llm_provider":"ollama","llm_reachable":true,"elevenlabs":true,"hardware_mode":"sim"}` | Health check |
| GET | `/api/events` | `{"ok":true,"events":[{title,start,end,location,tags}]}` | Campus events |
| GET | `/api/events/recommendations` | `{"ok":true,"events":[...], "reasons":[...]}` | Personalized recs |
| GET | `/api/calendar/summary` | `{"ok":true,"events":[{title,start,end}]}` | Calendar summary |
| POST | `/api/calendar/add` | `{"ok":true,"id":"..."}` | Add reminder/event |
| GET | `/api/profile` | `{"ok":true,"interests":[...],"preferences":{}}` | User profile |
| PUT | `/api/profile` | `{"ok":true}` | Update profile |
| GET | `/api/audio/tts/{filename}` | MP3/WAV file | Serve TTS audio |

### CORS Headers (Backend must set)
```
Access-Control-Allow-Origin: http://localhost:5173
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## CONTRACT 3: HardwareInterface (Software Abstraction)

Hardware is **optional**. The backend always talks to a `HardwareInterface` object. The default implementation is `SimHardware` which logs to console.

### HardwareInterface Methods

```python
class HardwareInterface:
    async def set_led_state(self, state: str, color: str = None) -> None:
        """Set LED mode. state: idle|listening|thinking|speaking|error. color: optional hex."""

    async def on_button_event(self, callback) -> None:
        """Register callback for button press events."""
```

### SimHardware (Default)

```python
class SimHardware(HardwareInterface):
    async def set_led_state(self, state, color=None):
        print(f"[SIM] LED -> {state} {color or ''}")

    async def on_button_event(self, callback):
        pass  # No button in sim mode
```

### ArduinoHardware (Phase 2, Optional)

If an Arduino is connected and `HARDWARE_MODE=arduino`, the backend uses `ArduinoHardware` which sends serial JSON commands:

```json
{"t":"cmd","id":"c001","action":"set_status","state":"listening"}
```

Arduino responds with ACK:
```json
{"t":"ack","id":"c001","ok":true}
```

Button events from Arduino:
```json
{"t":"event","type":"button_press","duration_ms":120}
```

**Rules:**
- Arduino sends ACK IMMEDIATELY on receipt
- Backend waits 400ms for ACK, retry once, then fail-open
- If serial port not found: auto-fall back to `SimHardware`

---

## SHARED CONTRACTS (Person 3 Maintains)

All schemas live in `shared/` and are the single source of truth for message shapes.

### `shared/ws_messages.schema.json`
Defines every WebSocket message type with required fields and examples.
Frontend and backend must conform to these shapes.

### `shared/tools.schema.json`
Defines every tool's request args and response shape.
Backend tool router must validate against these.

### `shared/events.schema.json`
Defines the event object shape used in `data/events_seed.json`.
Events service must load and validate against this schema.

### File Structure
```
shared/
  ws_messages.schema.json    # WS message definitions
  tools.schema.json          # Tool request/response definitions
  events.schema.json         # Event data schema
```

Person 3 creates these schemas. Person 1 and Person 2 reference them when implementing their message handlers.

---

## WAKE WORD AND AUDIO FLOW

### Flow Diagram
```
User taps "Start Listening"
  -> Frontend: Web Speech API starts continuous recognition
  -> Frontend: Shows listening indicator (pulsing mic icon)

User speaks: "Hey Vuddy, what's going on tonight?"
  -> Frontend: Transcript detected
  -> Frontend: Check prefix: starts with "hey vuddy" or "vuddy"?
     YES -> Strip wake word -> send {type:"transcript_final", text:"what's going on tonight?"}
     NO  -> Ignore (show brief "Say 'Hey Vuddy' first" hint)

Backend receives transcript_final:
  -> Send {type:"assistant_state", state:"thinking"}
  -> Call LLM provider with context + tools
  -> Execute any tool calls (get_events, etc.)
  -> Generate response text
  -> Send {type:"assistant_text", text:"..."}
  -> Call ElevenLabs TTS
  -> Send {type:"assistant_audio_ready", audio_url:"..."}
  -> Send {type:"assistant_state", state:"speaking"}
  -> Call HardwareInterface.set_led_state("speaking")

Frontend plays audio:
  -> On audio end -> state returns to listening
  -> If user speaks during playback:
     -> Send {type:"interrupt"}
     -> Stop audio playback immediately
     -> Process new utterance normally
```

### Push-to-Talk Fallback
If Web Speech API is unavailable (Firefox, HTTP without localhost):
- Show "Hold to Talk" button instead of continuous listening
- On button press: start recognition
- On button release: finalize transcript and apply wake-word gating
- Wake word gating still applies

---

## TOOL CONTRACTS (Backend Internal)

All tools are called by the LLM via function calling. Max 2 tool calls per turn.
Schemas live in `shared/tools.schema.json`.

| # | Tool | Args | Returns | Timeout |
|---|------|------|---------|---------|
| 1 | `get_events` | `time_range: str, tags: list[str]` | `{ok, events: [{title, start, end, location, tags, description}]}` | 2s |
| 2 | `get_recommendations` | `count: int=3` | `{ok, events: [...], reasons: [str]}` | 3s |
| 3 | `get_calendar_summary` | `hours_ahead: int=24` | `{ok, events: [{title, start, end}]}` | 2s |
| 4 | `add_calendar_item` | `title: str, time_iso: str, notes: str` | `{ok, id}` | 2s |
| 5 | `start_study_session` | `topic: str, duration_min: int=25` | `{ok, session_id, end_time}` | 1s |
| 6 | `stop_study_session` | `session_id: str` | `{ok, elapsed_min}` | 1s |
| 7 | `spotify_search_link` | `query: str` | `{ok, url, display_text}` | 1s |

### Tool Failure Policy
- Per-tool timeout shown above
- On timeout: return `{ok: false, error: "timeout"}`
- Max 1 retry per tool
- If all tools fail: generate response without tool results
- Unknown tool names: reject silently with structured error

---

## SHARED FILE PATHS (All Workstreams Must Agree)

```
data/
  events_seed.json                        # Person 3 creates, Person 1 loads
  fixtures/
    campus_events.json                    # Alternate seed data location
    calendar.json                         # Fallback calendar data
  profile/
    user_profile.json                     # User interests/preferences
  audio/
    tts/                                  # Person 1 writes, Person 2 reads via API
  memory/
    memory.db                             # SQLite, Person 1 manages
  db/
    vuddy.db                              # Main SQLite DB

shared/
  ws_messages.schema.json                 # Person 3 creates, all reference
  tools.schema.json                       # Person 3 creates, all reference
  events.schema.json                      # Person 3 creates, all reference

scripts/
  smoke_ws_client.py                      # Person 3 creates, all use for testing
```

---

## CANONICAL ENUM VALUES (Frozen - Use These Exact Strings)

**Assistant States** (backend sends to frontend + hardware):
`idle` `listening` `thinking` `speaking` `error`

**LED Modes** (hardware interface):
`pulse` `solid` `breathe` `off`

**Tool Names** (backend internal):
`get_events` `get_recommendations` `get_calendar_summary` `add_calendar_item` `start_study_session` `stop_study_session` `spotify_search_link`

**LLM Providers** (backend config):
`ollama` `patriotai`

**Hardware Modes** (backend config):
`sim` `arduino`

**WS Message Types - Backend->Frontend:**
`assistant_text` `assistant_audio_ready` `assistant_state` `tool_status` `error`

**WS Message Types - Frontend->Backend:**
`start_listening` `stop_listening` `transcript_final` `chat` `interrupt`

If a string is not in these lists, it is a bug.

---

## TRACK COMPLIANCE CHECKLIST

**Sponsor Track: Best Use of PatriotAI** (Cloudforce x Microsoft)

- [ ] **Use PatriotAI** as the primary intelligence layer (swap LLM_PROVIDER to patriotai before judging)
- [ ] **Follow Cloudforce** on LinkedIn: [linkedin.com/company/gocloudforce](https://linkedin.com/company/gocloudforce)
- [ ] **Post on LinkedIn** during/after hackathon tagging `@goCloudforce` with project description
- [ ] **Mention PatriotAI** in pitch deck and demo narration

**Internal Track: Education**
- [ ] Frame study session timer as **focus coaching / time management**
- [ ] Frame calendar features as **academic planning**
- [ ] Frame event recommendations as **campus engagement for student life**

**Optional Track: Most Likely To Be A Startup**
- [ ] Keep pitch product-like: "Every student deserves a campus concierge"
- [ ] Emphasize personalization, privacy-safe memory, voice-first UX

---

*Every person should have this file open at all times. When in doubt about a format, check here.*
