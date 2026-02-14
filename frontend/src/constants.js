// Assistant states (backend sends to frontend + hardware)
export const ASSISTANT_STATES = {
    IDLE: 'idle',
    LISTENING: 'listening',
    THINKING: 'thinking',
    SPEAKING: 'speaking',
    ERROR: 'error',
};

// WS Message Types - Frontend -> Backend
export const WS_SEND_TYPES = {
    START_LISTENING: 'start_listening',
    STOP_LISTENING: 'stop_listening',
    TRANSCRIPT_FINAL: 'transcript_final',
    CHAT: 'chat',
    INTERRUPT: 'interrupt',
};

// WS Message Types - Backend -> Frontend
export const WS_RECV_TYPES = {
    ASSISTANT_TEXT: 'assistant_text',
    ASSISTANT_AUDIO_READY: 'assistant_audio_ready',
    ASSISTANT_STATE: 'assistant_state',
    TOOL_STATUS: 'tool_status',
    ERROR: 'error',
};

// LLM Providers
export const LLM_PROVIDERS = {
    OLLAMA: 'ollama',
    PATRIOTAI: 'patriotai',
};

// Tab names
export const TABS = {
    HOME: 'home',
    EVENTS: 'events',
    STUDY: 'study',
    CALENDAR: 'calendar',
    SETTINGS: 'settings',
};

// Quick suggestion prompts
export const QUICK_SUGGESTIONS = [
    "What's on campus?",
    "Start studying",
    "My calendar",
    "Recommend events",
    "Play some music",
];

// Wake word variants (lowercase)
export const WAKE_WORDS = ['hey vuddy', 'vuddy'];

// API endpoints
export const API = {
    EVENTS: '/api/events',
    EVENTS_DISCOVER: '/api/events/discover',
    EVENTS_RECOMMENDATIONS: '/api/events/recommendations',
    EVENTS_SEARCH: '/api/events/search',
    CALENDAR_SUMMARY: '/api/calendar/summary',
    CALENDAR_ADD: '/api/calendar/add',
    CALENDAR_IMPORT_GOOGLE: '/api/calendar/import/google',
    PROFILE: '/api/profile',
    SCHOOL: '/api/school',
    HEALTH: '/health',
};

// WebSocket URL
export const WS_URL =
    (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
    window.location.host +
    '/ws';
