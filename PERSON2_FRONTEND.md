# PERSON 2: Frontend Developer
## Your job: Build the voice-first device UI with speech recognition, wake word gating, and audio playback.
## You own: `frontend/` folder. You touch nothing else.

**Read `WORKSTREAM_CONTRACTS.md` first. Keep it open at all times.**

---

## YOUR FILES (Create all of these)

```
frontend/
  index.html
  package.json
  vite.config.js
  public/
    vuddy-icon.svg
  src/
    main.jsx
    App.jsx
    AudioEngine.jsx
    components/
      WakeScreen.jsx
      HomeTab.jsx
      EventsTab.jsx
      StudyTab.jsx
      CalendarTab.jsx
      SettingsTab.jsx
      BottomNav.jsx
      MessageBubble.jsx
      ListeningIndicator.jsx
      ProviderBadge.jsx
      ToolStatusBadge.jsx
      ErrorToast.jsx
    hooks/
      useWebSocket.js
      useSpeechRecognition.js
      useAudio.js
    styles/
      index.css
    constants.js
```

---

## SETUP

```bash
npm create vite@latest ./ -- --template react
npm install
```

In `vite.config.js`:
```js
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true }
    }
  }
})
```

---

## KEY PRINCIPLES

1. **No dependency on hardware.** The UI never expects sensor data or hardware status. It works identically whether hardware is connected or not.
2. **Push-to-talk and interrupt must be rock solid.** These are the two most critical UX flows. If they break, the demo fails.
3. **Provider badge shows which LLM is active.** The backend tells us on WS connect.

---

## COMPONENT-BY-COMPONENT BUILD GUIDE

### 1. `WakeScreen.jsx` - First thing user sees

**Purpose:** Unlock mobile audio via user gesture + introduce the product.

```
Full-screen card:
  Background: dark gradient (#0a1628 -> #162544)
  Center: animated mic icon (pulsing scale 1.0->1.1, ease-in-out, 1.5s loop)
  Text: "Tap to start Vuddy" in #f0f4ff
  Subtitle: "Your campus desk buddy" in #8ba3c7

On tap anywhere:
  1. const ctx = new AudioContext();
  2. await ctx.resume();
  3. Store ctx in React context or ref (reuse for all audio)
  4. Transition to App (fade out splash, 300ms)
```

After this tap, all `audio.play()` calls work for the rest of the session. **This is mandatory.**

### 2. `App.jsx` - Main Layout

```
State:
  - activeTab: "home" | "events" | "study" | "calendar" | "settings"
  - isAwake: false (show WakeScreen until true)
  - isListening: boolean (speech recognition active)
  - assistantState: "idle" | "listening" | "thinking" | "speaking"
  - llmProvider: "ollama" (set from WS connect message)
  - wsConnected: boolean

Layout:
  if !isAwake -> <WakeScreen onWake={() => setIsAwake(true)} />
  else ->
    <AudioProvider>
      <div class="app-container">
        <ProviderBadge provider={llmProvider} />
        <ErrorToast />
        <main class="tab-content">
          {activeTab === "home" && <HomeTab />}
          {activeTab === "events" && <EventsTab />}
          {activeTab === "study" && <StudyTab />}
          {activeTab === "calendar" && <CalendarTab />}
          {activeTab === "settings" && <SettingsTab />}
        </main>
        <BottomNav activeTab onTabChange />
      </div>
    </AudioProvider>
```

### 3. `ProviderBadge.jsx` - LLM Provider Indicator

```
Small badge in top-right corner of app.
Shows which LLM provider is active:
  - "ollama" -> blue pill: "Ollama"
  - "patriotai" -> green pill: "PatriotAI"

Data source: `llm_provider` field from WS assistant_state on connect.
This lets judges see that PatriotAI is being used.
```

### 4. `HomeTab.jsx` - Main Voice Interaction Screen

This is the primary screen. Voice-first.

```
Layout (top to bottom):
  +-------------------------------+
  |  Assistant State Indicator    |  "Listening..." / "Thinking..." / "Speaking..."
  |                               |
  |  +-------------------------+  |
  |  |   Conversation Area     |  |  Scrollable message list
  |  |   (last 5 messages)     |  |
  |  +-------------------------+  |
  |                               |
  |  +-------------------------+  |
  |  |   Quick Suggestions     |  |  "What's on campus?" "Start studying" "My calendar"
  |  +-------------------------+  |
  |                               |
  |  +----------+  +-----------+  |
  |  | MIC/PTT  |  |  Type...  |  |  Mic button + text input fallback
  |  +----------+  +-----------+  |
  +-------------------------------+

Start/Stop Listening Button:
  - Tap to toggle listening on/off
  - When listening: shows pulsing blue glow, text "Listening... say 'Hey Vuddy'"
  - When idle: shows dim mic icon, text "Tap to start"

Push-to-Talk (if Web Speech API unavailable):
  - Button changes to "Hold to Talk"
  - Press and hold to record
  - Release to send (wake word gating still applies)

Interrupt:
  - If assistant is speaking (assistantState === "speaking"):
    - ANY new mic input or typed message triggers interrupt
    - Send {type:"interrupt"} FIRST
    - Stop audio playback IMMEDIATELY
    - Then send the new command
  - This must be rock solid. Test it repeatedly.

Text Input:
  - Always visible below mic button
  - "Type a command..." placeholder
  - Sends {type:"chat", text:"..."} (no wake word needed for typed input)
```

### 5. `EventsTab.jsx` - Campus Events

```
On mount: GET /api/events -> display events
Button: "Recommended for me" -> GET /api/events/recommendations

Each event card:
  - Title: bold, #f0f4ff
  - Time: 7:00 PM in #6ba3d6
  - Location: #8ba3c7, italic
  - Tags: small pills
  - Background: #162544

Recommended section includes reason strings.
```

### 6. `StudyTab.jsx` - Study Timer

```
Large circular timer (Pomodoro style)
  - Topic name centered
  - Time remaining in large font
  - Pulsing accent when < 5 min remaining

Controls:
  - "Start Session" button (topic + duration inputs)
  - "End Early" button
```

### 7. `CalendarTab.jsx` - Calendar Summary

```
On mount: GET /api/calendar/summary -> display events
"Add Reminder" button -> modal with title + time fields -> POST /api/calendar/add
```

### 8. `SettingsTab.jsx` - Preferences

```
- Wake word display: "Hey Vuddy" (read-only)
- Voice response length: Short / Normal / Detailed
- Privacy: "Save my preferences" toggle
- Interests: editable tags
- "About Vuddy": Powered by PatriotAI, version
```

### 9. `BottomNav.jsx` - 5 Tab Icons

```
Fixed bottom, height: 56px, bg: #0a1628, border-top: 1px #162544
Tabs: Home | Events | Study | Calendar | Settings
Active: accent blue (#4A90D9)
Inactive: #8ba3c7
```

### 10. `ListeningIndicator.jsx` - Mic Feedback

```
States:
  - idle: Dim mic icon, "Tap to start"
  - listening: Pulsing blue glow, "Listening... say 'Hey Vuddy'"
  - thinking: Spinning dots, "Thinking..."
  - speaking: Sound wave animation, "Speaking..."
```

### `ErrorToast.jsx`
```
On WS "error" message:
  - recoverable=true: yellow warning bar, auto-dismiss 3s
  - recoverable=false: red error bar, persist until dismissed
```

---

## HOOKS

### `useWebSocket.js`
```
Connect to ws://localhost:8000/ws on mount
Parse incoming message.type, dispatch to correct handler
On connect message: extract llm_provider field for ProviderBadge
Reconnect on disconnect (1s, 2s, 4s exponential backoff, max 10s)
Expose: { sendMessage, lastMessage, isConnected, llmProvider }
```

### `useSpeechRecognition.js` - THE CRITICAL HOOK
```
Uses Web Speech API (window.SpeechRecognition or webkitSpeechRecognition)

API check on mount:
  if (!window.SpeechRecognition && !window.webkitSpeechRecognition):
    return { supported: false } -> App shows push-to-talk fallback

On result (final):
  - Check wake word: does transcript.toLowerCase() start with "hey vuddy" or "vuddy"?
  - YES: strip wake word, call onCommand(strippedText)
  - NO: show hint "Say 'Hey Vuddy' first", do NOT send to backend

Expose: { isListening, transcript, startListening, stopListening, supported }
```

### `useAudio.js` - Audio Playback Engine
```
States: IDLE | LOADING | PLAYING

On "assistant_audio_ready" message:
  1. Fetch audio from audio_url
  2. Decode via AudioContext
  3. Play through speakers

Interrupt:
  - Stop current audio immediately
  - Reset state to IDLE

Expose: { audioState, playAudio, stopAudio }
```

---

## CAMPUS DARK THEME - CSS Tokens

```css
:root {
  --bg-deep: #0a1628;
  --bg-surface: #162544;
  --bg-elevated: #1e3460;
  --accent-blue: #4A90D9;
  --accent-teal: #38B2AC;
  --accent-glow: rgba(74, 144, 217, 0.15);
  --text-primary: #f0f4ff;
  --text-muted: #8ba3c7;
  --text-dim: #5a7599;
  --accent-color: #4A90D9;
  --font-main: 'Inter', -apple-system, system-ui, sans-serif;
  --font-size-base: 16px;
  --font-size-sm: 14px;
  --font-size-xs: 12px;
  --font-size-lg: 20px;
  --font-size-xl: 28px;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --max-width: 480px;
  --nav-height: 56px;
  --tap-target-min: 44px;
  --transition-fast: 150ms ease;
  --transition-normal: 300ms ease;
}
```

---

## CRITICAL REMINDERS

1. **WakeScreen MUST be the first screen (unlocks AudioContext)**
2. **WebSocket message `type` field must match `WORKSTREAM_CONTRACTS.md` exactly**
3. **Wake word gating happens in the FRONTEND, not the backend**
4. **Push-to-talk and interrupt must be rock solid**
5. **No hardware dependency: UI works identically with or without Arduino**
6. **ProviderBadge shows judges which LLM is active**
7. **Send `interrupt` BEFORE `chat`/`transcript_final` when audio is playing**
8. **Speech recognition requires HTTPS or localhost**
9. **Font size 16px minimum on inputs (prevents iOS zoom)**
