# VUDDY - CAMPUS DESK BUDDY MASTER SPECIFICATION
## The One Document. Every Feature. Zero Ambiguity.
### Feb 13, 2026 | HackFax x PatriotHacks | Sponsor Track: Best Use of PatriotAI

---

## WHAT IS VUDDY

A voice-first AI campus assistant that runs as a web app (browser-based "smart speaker" experience). It uses a swappable LLM backend (**Ollama** for dev, **PatriotAI** for judging), **ElevenLabs** for voice output, and responds to the wake word **"Hey Vuddy"**. It helps students find campus events, plan study sessions, manage their calendar, and get personalized recommendations.

**Software-first:** The end-to-end voice loop is the product. Hardware (LED + button) is optional and simulated by default.

---

## TEAM STRUCTURE (3 People)

| Person | Role | Owns |
|--------|------|------|
| Person 1 | Backend orchestrator | `backend/` |
| Person 2 | Frontend kiosk UI | `frontend/` |
| Person 3 | Integration + Data + QA | `shared/`, `scripts/`, `data/`, docs |

Person 1 and Person 2 build the product. Person 3 builds the glue that makes merging painless.

---

## HARDWARE

| Item | Spec |
|------|------|
| Laptop | Any laptop with Chrome browser + mic |
| Phone | Optional, can run frontend on phone browser |
| Arduino | Optional, simulated by default (LED ring + button only if time allows) |

---

## AI STACK

| Component | Purpose | Provider |
|-----------|---------|----------|
| LLM | Conversational brain + tool calling | Ollama (dev) / PatriotAI (judging) |
| ElevenLabs | Text-to-speech (natural voice) | ElevenLabs API |
| Web Speech API | Speech-to-text (in browser) | Browser native |

**No GPU required.** Ollama runs CPU-only for dev. PatriotAI is a cloud API.

---

## VOICE INTERACTION

### Wake Word
- **"Hey Vuddy"** or **"Vuddy"**, detected via browser speech recognition
- Wake word gating is done in the frontend (prefix match on transcript)
- If no wake word detected: ignore utterance, show hint
- Typed input does NOT require wake word

### Flow
```
User taps "Start" -> continuous speech recognition begins
User says "Hey Vuddy, what's happening tonight?"
-> Frontend strips wake word -> sends "what's happening tonight?" to backend
-> Backend calls LLM provider with tools
-> Backend generates response text
-> Backend calls ElevenLabs TTS
-> Frontend plays audio response
-> User hears Vuddy answer
```

### Interrupt
- If user speaks while Vuddy is talking:
  - Frontend sends `interrupt` -> stops audio -> processes new command
  - Backend cancels in-flight request if possible

### Push-to-Talk Fallback
- If Web Speech API unavailable: show "Hold to Talk" button
- Wake word gating still applies

---

## TOOLS (7 Functions)

LLM uses function calling. Max 2 tool calls per turn.

| # | Tool | Description | Timeout |
|---|------|-------------|---------|
| 1 | `get_events` | Campus events by time range + tags | 2s |
| 2 | `get_recommendations` | Personalized event picks | 3s |
| 3 | `get_calendar_summary` | Calendar events ahead | 2s |
| 4 | `add_calendar_item` | Add reminder/event | 2s |
| 5 | `start_study_session` | Start Pomodoro timer | 1s |
| 6 | `stop_study_session` | End study session | 1s |
| 7 | `spotify_search_link` | Generate Spotify link | 1s |

Tool schemas are defined in `shared/tools.schema.json` (Person 3 maintains).

---

## TEXT-TO-SPEECH (ElevenLabs)

- Backend calls ElevenLabs API via `httpx`
- Returns MP3 audio
- Files named by hash: `sha256(voice_id + text)[:16].mp3` (cache hits)
- Cached audio served via REST at `/api/audio/tts/`
- Max text length: 500 chars
- Fallback: text shown in chat, browser `speechSynthesis` as emergency backup

---

## CAMPUS EVENTS

- **Primary:** `data/events_seed.json` (15 seeded events, always available)
- Schema defined in `shared/events.schema.json`
- Personalization via user profile interests (keyword overlap scoring)

---

## STUDY MODE

- `start_study_session(topic, duration_min)`, default 25 min
- Backend tracks session state in memory
- Frontend shows timer UI with countdown

---

## CALENDAR

- Default: `data/fixtures/calendar.json`
- Optional: Google Calendar API via service account
- Add items stored in local JSON

---

## SPOTIFY

- Generate Spotify search URLs (no OAuth)
- Frontend shows "Open in Spotify" link/card

---

## WEBSOCKET PROTOCOL

Schemas defined in `shared/ws_messages.schema.json`.

### Backend -> Frontend

| type | Fields | When |
|------|--------|------|
| `assistant_text` | `text, tool_results` | After LLM response |
| `assistant_audio_ready` | `audio_url, format` | After ElevenLabs TTS |
| `assistant_state` | `state, llm_provider?` | On state change |
| `tool_status` | `tool, status` | During tool execution |
| `error` | `message, recoverable` | On any failure |

### Frontend -> Backend

| type | Fields | When |
|------|--------|------|
| `start_listening` | (none) | User taps Start |
| `stop_listening` | (none) | User taps Stop |
| `transcript_final` | `text` | Wake-word-gated utterance |
| `chat` | `text` | Typed input |
| `interrupt` | (none) | User interrupts |

---

## HARDWARE INTERFACE

Hardware is optional. Backend always talks to a `HardwareInterface` object.

| Mode | Implementation | When |
|------|---------------|------|
| `sim` (default) | `SimHardware` | Logs LED states to console |
| `arduino` | `ArduinoHardware` | Talks to real Arduino via serial |

Set via `HARDWARE_MODE` env var. Default is `sim`.

---

## FRONTEND (React + Vite)

### Navigation: Bottom Tab Bar (5 tabs)
| Tab | Icon | Screen |
|-----|------|--------|
| Home | Home | Voice interaction + conversation |
| Events | Calendar | Campus events + recommendations |
| Study | Book | Study timer |
| Calendar | Date | Calendar summary + add |
| Settings | Gear | Preferences, interests, privacy |

### Campus Dark Theme
```
Backgrounds:   #0a1628 (deep) -> #162544 (surface) -> #1e3460 (elevated)
Accents:        #4A90D9 (blue) / #38B2AC (teal)
Text:           #f0f4ff (primary) / #8ba3c7 (muted)
```

### Provider Badge
- Top-right corner shows active LLM provider ("Ollama" or "PatriotAI")
- Data from WS connect message `llm_provider` field

---

## BACKEND (Python FastAPI)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, REST + WebSocket routes |
| `llm_provider.py` | LLM abstraction (Ollama + PatriotAI) |
| `brain.py` | Context building, tool routing, orchestration |
| `elevenlabs_tts.py` | ElevenLabs TTS + caching |
| `events_service.py` | Campus events from seeded JSON |
| `recommender.py` | Personalized event ranking |
| `study_service.py` | Study session timer |
| `calendar_service.py` | Calendar summary + add |
| `profile_store.py` | User preferences JSON store |
| `hardware_interface.py` | SimHardware (default) / ArduinoHardware |
| `tools.py` | Tool router + definitions |
| `spotify_links.py` | Spotify URL generator |

---

## FALLBACK MATRIX

| Component | Normal | Fallback |
|-----------|--------|----------|
| LLM | Ollama (dev) / PatriotAI (judging) | Error message to user |
| TTS | ElevenLabs API | Browser speechSynthesis |
| Speech Recognition | Web Speech API | Push-to-talk + typed input |
| Events | Seeded JSON | Always available |
| Calendar | Google Calendar API | Fixture JSON |
| Hardware | SimHardware (default) | Always available (no device needed) |
| Spotify | Link generation | Always available (URL gen) |

**Every component has a fallback. The demo cannot fail.**

---

## DEMO SCRIPT (2:00)

| Time | Segment | What Happens |
|------|---------|-------------|
| 0:00 | Wake | Tap "Start Vuddy" -> intro voice greeting |
| 0:15 | Voice Chat | "Hey Vuddy, what's going on around campus tonight?" -> lists events |
| 0:35 | Recommendation | "Hey Vuddy, recommend something for me" -> personalized pick with reason |
| 0:50 | Study Mode | "Hey Vuddy, start a 25 minute study session for CS 310" -> timer starts |
| 1:05 | Calendar | "Hey Vuddy, what's on my calendar tomorrow?" -> reads events |
| 1:20 | Add Reminder | "Hey Vuddy, add a reminder: submit homework at 11 PM" -> confirmed |
| 1:35 | Spotify | "Hey Vuddy, play some lo-fi beats" -> Spotify link shown |
| 1:45 | Pitch | "Powered by PatriotAI. Every student deserves a campus concierge." |
| 2:00 | END | |

---

## PROJECT STRUCTURE

```
hackfax_02_2026/
  backend/
    main.py
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
    spotify_links.py
    constants.py
    requirements.txt
  frontend/
    src/
      App.jsx
      components/
        WakeScreen.jsx
        HomeTab.jsx
        EventsTab.jsx
        StudyTab.jsx
        CalendarTab.jsx
        SettingsTab.jsx
        ProviderBadge.jsx
      hooks/
        useSpeechRecognition.js
        useWebSocket.js
        useAudio.js
      styles/
        index.css
    index.html
    package.json
    vite.config.js
  shared/                        # Person 3 owns
    ws_messages.schema.json
    tools.schema.json
    events.schema.json
  scripts/                       # Person 3 owns
    smoke_ws_client.py
  data/
    events_seed.json
    fixtures/
      campus_events.json
      calendar.json
    profile/
      user_profile.json
    audio/tts/
    db/
  arduino/                       # Optional (Phase 2)
    vuddy/vuddy.ino
  .env.example
  setup.sh
  MASTER_SPEC.md
  WORKSTREAM_CONTRACTS.md
  PERSON1_BACKEND.md
  PERSON2_FRONTEND.md
  PERSON3_ARDUINO.md             # Integration + Data + QA doc
  README.md
```

---

## ENVIRONMENT VARIABLES (.env)

```bash
# LLM Provider
LLM_PROVIDER=ollama              # "ollama" (default) or "patriotai"

# Ollama (default)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

# PatriotAI (for judging)
PATRIOTAI_API_KEY=your_key
PATRIOTAI_BASE_URL=https://api.patriotai.com/v1
PATRIOTAI_MODEL=patriotai-default

# ElevenLabs
ELEVENLABS_API_KEY=your_key
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB

# Config
WAKE_WORD=hey vuddy
EVENTS_DATA_PATH=./data/events_seed.json

# Hardware (optional)
HARDWARE_MODE=sim                # "sim" (default) or "arduino"
SERIAL_PORT=/dev/ttyUSB0
```

---

## TRACK COMPLIANCE

### Sponsor: Best Use of PatriotAI (Cloudforce x Microsoft)
- [ ] PatriotAI is primary intelligence (set `LLM_PROVIDER=patriotai`)
- [ ] Follow Cloudforce on LinkedIn
- [ ] Post + tag @goCloudforce

### Internal: Education
- Study timer = focus coaching
- Calendar = academic planning
- Events = campus engagement

---

*This is the complete specification. Every feature. Every protocol. Every config. Build from this document.*
