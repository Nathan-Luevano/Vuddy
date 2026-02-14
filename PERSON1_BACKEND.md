# PERSON 1: Backend Developer
## Your job: Build the brain, voice, and orchestration for a voice-first campus assistant.
## You own: `backend/` folder. You touch nothing else.

**Read `WORKSTREAM_CONTRACTS.md` first. Keep it open at all times.**

---

## YOUR FILES (Create all of these)

```
backend/
  main.py
  constants.py
  llm_provider.py
  brain.py
  elevenlabs_tts.py
  events_service.py
  recommender.py
  study_service.py
  calendar_service.py
  profile_store.py
  hardware_interface.py
  tools.py
  requirements.txt
  spotify_links.py
```

---

## FILE-BY-FILE BUILD GUIDE

### 1. `requirements.txt`
```
fastapi
uvicorn[standard]
websockets
aiofiles
aiosqlite
httpx
pyserial
python-dotenv
pydantic
```

### 1b. `constants.py`
Frozen enum values. Import these everywhere instead of using raw strings.
```python
ASSISTANT_STATES = ["idle", "listening", "thinking", "speaking", "error"]
LED_MODES = ["pulse", "solid", "breathe", "off"]
LLM_PROVIDERS = ["ollama", "patriotai"]
HARDWARE_MODES = ["sim", "arduino"]
TOOL_NAMES = [
    "get_events", "get_recommendations", "get_calendar_summary",
    "add_calendar_item", "start_study_session", "stop_study_session",
    "spotify_search_link"
]
WS_TYPES_OUT = ["assistant_text", "assistant_audio_ready", "assistant_state", "tool_status", "error"]
WS_TYPES_IN = ["start_listening", "stop_listening", "transcript_final", "chat", "interrupt"]
```

### 2. `llm_provider.py` - LLM Provider Abstraction

This module defines a common interface and two implementations. The active provider is selected by `LLM_PROVIDER` env var.

```python
import os

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

class LLMProvider:
    """Base class for LLM providers."""
    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        raise NotImplementedError
    async def health_check(self) -> bool:
        raise NotImplementedError
    @property
    def name(self) -> str:
        raise NotImplementedError
```

#### OllamaProvider (default, implemented now)
```python
class OllamaProvider(LLMProvider):
    """Ollama local LLM. Works out of the box with `ollama serve`."""

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.client = httpx.AsyncClient(timeout=15.0)

    @property
    def name(self) -> str:
        return "ollama"

    async def chat(self, messages, tools=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"num_ctx": 4096},
            "keep_alive": -1,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        resp = await self.client.post(f"{self.base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {})

    async def health_check(self):
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False
```

#### PatriotAIProvider (stubbed, same interface)
```python
class PatriotAIProvider(LLMProvider):
    """PatriotAI cloud LLM. Swap to this for judging."""

    def __init__(self):
        self.base_url = os.getenv("PATRIOTAI_BASE_URL", "https://api.patriotai.com/v1")
        self.api_key = os.getenv("PATRIOTAI_API_KEY", "")
        self.model = os.getenv("PATRIOTAI_MODEL", "patriotai-default")
        self.client = httpx.AsyncClient(timeout=15.0)

    @property
    def name(self) -> str:
        return "patriotai"

    async def chat(self, messages, tools=None):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        resp = await self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]

    async def health_check(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = await self.client.get(f"{self.base_url}/models", headers=headers)
            return resp.status_code == 200
        except Exception:
            return False
```

#### Factory
```python
def create_llm_provider() -> LLMProvider:
    if LLM_PROVIDER == "patriotai":
        return PatriotAIProvider()
    return OllamaProvider()  # default
```

### 3. `elevenlabs_tts.py` - Voice Generation
- Use `httpx` to call ElevenLabs text-to-speech API
- Accept text + voice_id -> output MP3 to `data/audio/tts/`
- Filename: `sha256(voice_id + text)[:16].mp3`
- If file exists (cache hit): return path immediately
- Max text length: 500 chars. Truncate if longer.
- Expose `async def synthesize(text: str) -> str` (returns file path)

**Fallback:** If ElevenLabs API fails, return text-only response (frontend shows text, uses browser speechSynthesis as emergency backup).

### 4. `brain.py` - Conversation Orchestrator
**One main method:**
```python
async def process_message(text: str, ws) -> None:
```

**Flow:**
1. Send `{"type":"assistant_state","state":"thinking"}` via WS
2. Call `hardware_interface.set_led_state("thinking")`
3. Retrieve user profile from `profile_store.py`
4. Build messages array: system prompt + profile context + chat history + user message
5. Call `llm_provider.chat()` with tools
6. If tool_calls returned:
   a. Send `{"type":"tool_status","tool":name,"status":"calling"}` via WS
   b. Execute tool via `tools.py`
   c. Send `{"type":"tool_status","tool":name,"status":"done"}` via WS
   d. Append tool result to messages
   e. Call `llm_provider.chat()` again without tools for final response
7. Send `{"type":"assistant_text","text":"..."}` via WS
8. Generate TTS audio via `elevenlabs_tts.py`
9. Send `{"type":"assistant_audio_ready","audio_url":"..."}` via WS
10. Send `{"type":"assistant_state","state":"speaking"}` via WS
11. Call `hardware_interface.set_led_state("speaking")`

**Chat history:** Keep last 10 messages in memory. Trim older ones.

### 5. `tools.py` - Tool Router
Define 7 tools as OpenAI-compatible function definitions. Each tool has an execute function.
**Schemas must match `shared/tools.schema.json`** (Person 3 maintains the schema).

Max 2 tool calls per turn. 1 retry on failure.

### 6. `events_service.py` - Campus Events
- Load seeded events from path in `EVENTS_DATA_PATH` env var (default: `data/events_seed.json`)
- Schema must match `shared/events.schema.json`
- `get_events(time_range, tags)` -> filter and return matching events
- Time range parsing: "tonight" = 5PM-midnight, "tomorrow" = next day, "this weekend" = Sat+Sun

### 7. `recommender.py` - Personalized Recommendations
- Load user profile from `profile_store.py`
- Score events by interest match (simple keyword overlap)
- Return top-N events with reason strings

### 8. `study_service.py` - Study Session Timer
- In-memory session store
- `start_session(topic, duration_min)` -> create session, return `{session_id, end_time}`
- `stop_session(session_id)` -> mark inactive, return `{elapsed_min}`

### 9. `calendar_service.py` - Calendar Summary
- Load from `data/fixtures/calendar.json` as default
- Optional: Google Calendar API via service account
- `get_summary(hours_ahead)` -> list of `{title, start, end}`
- `add_item(title, time_iso, notes)` -> append to local JSON store

### 10. `profile_store.py` - User Preferences
- JSON file at `data/profile/user_profile.json`
- Default: `{"interests": [], "preferred_times": [], "study_habits": {}, "preferences": {}}`
- Privacy: only update when user explicitly confirms

### 11. `hardware_interface.py` - Hardware Abstraction

This module provides a clean interface that the rest of the backend uses. **The backend can always run with no serial device connected.**

```python
import os

HARDWARE_MODE = os.getenv("HARDWARE_MODE", "sim")

class HardwareInterface:
    async def set_led_state(self, state: str, color: str = None) -> None:
        raise NotImplementedError
    async def on_button_event(self, callback) -> None:
        raise NotImplementedError

class SimHardware(HardwareInterface):
    """Default simulator. Logs to console. No real hardware needed."""
    async def set_led_state(self, state, color=None):
        print(f"[SIM-HW] LED -> state={state} color={color or 'default'}")
    async def on_button_event(self, callback):
        pass  # No button in sim mode

class ArduinoHardware(HardwareInterface):
    """Phase 2. Talks to Arduino via serial. Only used if HARDWARE_MODE=arduino."""
    # ... serial bridge logic from previous spec ...
    pass

def create_hardware() -> HardwareInterface:
    if HARDWARE_MODE == "arduino":
        try:
            return ArduinoHardware()
        except Exception as e:
            print(f"[HW] Arduino init failed ({e}), falling back to SimHardware")
            return SimHardware()
    return SimHardware()
```

**Key point:** `SimHardware` is the default. The backend runs perfectly without any serial device.

### 12. `spotify_links.py` - Spotify Link Generator
- No OAuth required
- `search_link(query)` -> `{"ok": true, "url": "https://open.spotify.com/search/...", "display_text": "..."}`

### 13. `main.py` - FastAPI App
**Startup:**
1. Load .env
2. Create LLM provider via `create_llm_provider()`
3. Create hardware via `create_hardware()` (defaults to SimHardware)
4. Init profile_store
5. Load events data
6. Verify ElevenLabs API key is set

**Health endpoint returns:**
```json
{"ok": true, "llm_provider": "ollama", "llm_reachable": true, "elevenlabs": true, "hardware_mode": "sim"}
```

**WebSocket `/ws`:**
- On connect: send `{"type":"assistant_state","state":"idle","wake_word":"hey vuddy","llm_provider":"ollama"}`
- On `transcript_final` or `chat` -> `brain.process_message()`
- On `interrupt` -> cancel in-flight LLM request, reset state
- On `start_listening` -> `hardware_interface.set_led_state("listening")`

---

## ACCEPTANCE CRITERIA

### Health Check
```bash
curl http://localhost:8000/health
# -> {"ok":true,"llm_provider":"ollama","llm_reachable":true,"elevenlabs":true,"hardware_mode":"sim"}
```

### WebSocket Chat (use Person 3's smoke test)
```bash
python scripts/smoke_ws_client.py
# Or manually:
echo '{"type":"chat","text":"what events are happening tonight?"}' | websocat ws://localhost:8000/ws
```

### Events API
```bash
curl http://localhost:8000/api/events
# -> {"ok":true,"events":[{"title":"Game Night",...},...]}"
```

---

## CRITICAL REMINDERS

1. **EVERY LLM call goes through `llm_provider.py`** (never call Ollama or PatriotAI directly)
2. **EVERY hardware call goes through `hardware_interface.py`** (SimHardware by default)
3. **ElevenLabs TTS must cache by content hash**
4. **WebSocket message format must EXACTLY match `WORKSTREAM_CONTRACTS.md`**
5. **Tool schemas must match `shared/tools.schema.json`**
6. **Import enum values from `constants.py`, never use raw strings**
7. **Backend runs with ZERO hardware, ZERO GPU, just API keys**
