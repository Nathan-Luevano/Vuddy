# Vuddy - Your Campus Desk Buddy

A voice-first AI campus assistant powered by **PatriotAI**. Ask about campus events, plan your study sessions, manage your calendar, and get personalized recommendations, all by voice.

**Built for HackFax x PatriotHacks 2026** (Feb 13-15, George Mason University)

**Sponsor Track: Best Use of PatriotAI** (Cloudforce x Microsoft)

## What is Vuddy?

Vuddy is an Alexa-like campus desk buddy that lives on your laptop (or phone browser). It listens for "Hey Vuddy", understands your request using an LLM (Ollama for dev, PatriotAI for judging), and responds with a natural voice via ElevenLabs. It knows what's happening on campus, helps you study, and manages your schedule.

## Features

- Voice-First: Wake word "Hey Vuddy" with continuous speech recognition
- Swappable LLM: Ollama for local dev, PatriotAI for judging (one env var swap)
- Natural Voice: ElevenLabs text-to-speech for lifelike responses
- Campus Events: "What's going on around campus tonight?"
- Study Buddy: Pomodoro-style study timer with focus coaching
- Calendar: "What's on my calendar tomorrow?" + add reminders
- Spotify Links: "Play some lo-fi beats" opens Spotify
- Personalized: Learns your interests for better recommendations
- Privacy-Safe: Preferences updated only with your permission

## Team Structure

| Person | Role | Owns |
|--------|------|------|
| Person 1 | Backend orchestrator | `backend/` |
| Person 2 | Frontend kiosk UI | `frontend/` |
| Person 3 | Integration + Data + QA | `shared/`, `scripts/`, `data/` |

## Track Alignment

### Sponsor Track: Best Use of PatriotAI
- [x] PatriotAI is the primary intelligence layer (swap `LLM_PROVIDER=patriotai`)
- [ ] Follow Cloudforce on LinkedIn
- [ ] Post on LinkedIn tagging @goCloudforce

### Internal Track: Education
- Study session timer = focus coaching / time management
- Calendar features = academic planning
- Event recommendations = campus engagement for student life

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite (voice device UI) |
| Backend | Python FastAPI + WebSocket |
| AI | Ollama (dev) / PatriotAI (judging) + ElevenLabs (TTS) |
| Hardware | Optional: Arduino LED + Button (simulated by default) |
| Data | Seeded campus events JSON + SQLite |

## Project Structure

```
hackfax_02_2026/
  backend/              # Person 1: FastAPI server
    main.py             # App entry point + routes
    llm_provider.py     # LLM abstraction (Ollama + PatriotAI)
    brain.py            # Conversation orchestrator
    hardware_interface.py  # SimHardware (default) / ArduinoHardware
    requirements.txt
  frontend/             # Person 2: React + Vite voice UI
    src/
      App.jsx
      components/
        HomeTab.jsx
        ProviderBadge.jsx
      hooks/
        useSpeechRecognition.js
        useWebSocket.js
  shared/               # Person 3: Contract schemas
    ws_messages.schema.json
    tools.schema.json
    events.schema.json
  scripts/              # Person 3: Test harnesses
    smoke_ws_client.py
  data/
    events_seed.json    # Seeded campus events (15 events)
  arduino/              # Optional, Phase 2
    vuddy/vuddy.ino
  .env.example
  setup.sh
  README.md
```

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env  # Fill in ElevenLabs API key, set LLM_PROVIDER
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Smoke Test
```bash
python scripts/smoke_ws_client.py
```

### Demo Flow
1. Open `http://localhost:5173` in Chrome
2. Tap "Start Vuddy" to unlock audio
3. Click the mic button, say "Hey Vuddy, what's going on around campus tonight?"
4. Vuddy responds with voice + text

### Arduino (Optional, only if time allows)
1. Set `HARDWARE_MODE=arduino` in `.env`
2. Open `arduino/vuddy/vuddy.ino` in Arduino IDE
3. Upload to Arduino
4. Backend auto-detects and controls LEDs

## Environment Variables

See `.env.example` for all configuration:
- `LLM_PROVIDER` - `ollama` (default) or `patriotai`
- `ELEVENLABS_API_KEY` - Required for TTS
- `HARDWARE_MODE` - `sim` (default) or `arduino`
- Everything else has sensible defaults

## Team

Built at HackFax x PatriotHacks 2026, powered by PatriotAI.
