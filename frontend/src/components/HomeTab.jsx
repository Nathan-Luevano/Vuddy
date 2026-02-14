import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { ASSISTANT_STATES, WS_SEND_TYPES, WS_RECV_TYPES, QUICK_SUGGESTIONS } from '../constants';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { useAudio } from '../hooks/useAudio';
import { useAudioContext } from '../AudioEngine';
import MessageBubble from './MessageBubble';
import ToolStatusBadge from './ToolStatusBadge';

const CONVERSATIONS_KEY_PREFIX = 'vuddy_conversations';
const ACTIVE_CONVERSATION_KEY_PREFIX = 'vuddy_active_conversation';
const LEGACY_MESSAGES_KEY = 'vuddy_home_messages';

function newConversation() {
    const now = new Date().toISOString();
    return {
        id: `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        title: 'New conversation',
        createdAt: now,
        updatedAt: now,
        messages: [],
    };
}

function deriveTitle(messages) {
    const firstUser = messages.find((msg) => msg?.role === 'user' && typeof msg.text === 'string' && msg.text.trim());
    if (!firstUser) return 'New conversation';
    return firstUser.text.trim().slice(0, 48);
}

function normalizeConversation(raw) {
    if (!raw || typeof raw !== 'object') return null;
    const id = typeof raw.id === 'string' ? raw.id : `conv_${Date.now()}`;
    const messages = Array.isArray(raw.messages) ? raw.messages : [];
    const createdAt = typeof raw.createdAt === 'string' ? raw.createdAt : new Date().toISOString();
    const updatedAt = typeof raw.updatedAt === 'string' ? raw.updatedAt : createdAt;
    const title = typeof raw.title === 'string' && raw.title.trim() ? raw.title.trim() : deriveTitle(messages);
    return { id, messages, createdAt, updatedAt, title };
}

function getStorageKeys(schoolKey) {
    const safeSchool = (schoolKey || 'default').toLowerCase().replace(/\s+/g, '_');
    return {
        conversationsKey: `${CONVERSATIONS_KEY_PREFIX}_${safeSchool}`,
        activeConversationKey: `${ACTIVE_CONVERSATION_KEY_PREFIX}_${safeSchool}`,
    };
}

function loadConversations(schoolKey) {
    const { conversationsKey } = getStorageKeys(schoolKey);
    try {
        const raw = window.localStorage.getItem(conversationsKey);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) {
                const cleaned = parsed.map(normalizeConversation).filter(Boolean);
                if (cleaned.length > 0) return cleaned;
            }
        }
    } catch {
        // ignore
    }

    try {
        const legacyRaw = window.localStorage.getItem(LEGACY_MESSAGES_KEY);
        const legacy = legacyRaw ? JSON.parse(legacyRaw) : [];
        if (Array.isArray(legacy) && legacy.length > 0) {
            const conv = newConversation();
            conv.messages = legacy;
            conv.title = deriveTitle(legacy);
            return [conv];
        }
    } catch {
        // ignore
    }

    return [newConversation()];
}

export default function HomeTab({ sendMessage, lastMessage, assistantState, schoolKey = 'default' }) {
    const { conversationsKey, activeConversationKey } = useMemo(() => getStorageKeys(schoolKey), [schoolKey]);
    const [conversations, setConversations] = useState(() => loadConversations(schoolKey));
    const [activeConversationId, setActiveConversationId] = useState(() => {
        try {
            return window.localStorage.getItem(activeConversationKey) || null;
        } catch {
            return null;
        }
    });
    const [historyOpen, setHistoryOpen] = useState(false);
    const [historyQuery, setHistoryQuery] = useState('');
    const [textInput, setTextInput] = useState('');
    const [speechError, setSpeechError] = useState('');
    const [autoSpeak, setAutoSpeak] = useState(() => {
        try {
            const saved = window.localStorage.getItem('vuddy_auto_speak');
            return saved === null ? true : saved === 'true';
        } catch {
            return true;
        }
    });
    const [toolStatuses, setToolStatuses] = useState([]);
    const pendingConversationIdRef = useRef(null);
    const activeConversationIdRef = useRef(null);
    const lastUserSubmissionRef = useRef({ text: '', at: 0 });
    const lastAssistantAppendRef = useRef({ text: '', at: 0 });
    const conversationRef = useRef(null);

    const audioContextRef = useAudioContext();
    const {
        audioState,
        playAudio,
        stopAudio,
        pauseAudio,
        resumeAudio,
        unlockAudio,
        playPendingAudio,
        isAudioUnlocked,
        autoplayBlocked,
        hasPendingAudio,
        AUDIO_STATE,
    } = useAudio(audioContextRef);

    useEffect(() => {
        setConversations(loadConversations(schoolKey));
        try {
            setActiveConversationId(window.localStorage.getItem(activeConversationKey) || null);
        } catch {
            setActiveConversationId(null);
        }
        pendingConversationIdRef.current = null;
        setHistoryQuery('');
        setToolStatuses([]);
    }, [schoolKey, activeConversationKey]);

    useEffect(() => {
        if (!activeConversationId || !conversations.some((c) => c.id === activeConversationId)) {
            setActiveConversationId(conversations[0]?.id || null);
        }
    }, [conversations, activeConversationId]);

    useEffect(() => {
        try {
            window.localStorage.setItem(conversationsKey, JSON.stringify(conversations.slice(0, 100)));
            window.localStorage.removeItem(LEGACY_MESSAGES_KEY);
        } catch (e) {
            console.warn('[HomeTab] Failed to persist conversations:', e);
        }
    }, [conversations, conversationsKey]);

    useEffect(() => {
        if (!activeConversationId) return;
        try {
            window.localStorage.setItem(activeConversationKey, activeConversationId);
        } catch {
            // ignore
        }
    }, [activeConversationId, activeConversationKey]);

    useEffect(() => {
        try {
            window.localStorage.setItem('vuddy_auto_speak', String(autoSpeak));
        } catch {
            // ignore
        }
        if (!autoSpeak) stopAudio();
    }, [autoSpeak, stopAudio]);

    const activeConversation = useMemo(
        () => conversations.find((c) => c.id === activeConversationId) || conversations[0] || null,
        [conversations, activeConversationId]
    );
    const messages = activeConversation?.messages || [];

    useEffect(() => {
        activeConversationIdRef.current = activeConversation?.id || null;
    }, [activeConversation?.id]);

    const updateConversation = useCallback((conversationId, updater) => {
        setConversations((prev) => prev.map((conv) => (
            conv.id === conversationId ? updater(conv) : conv
        )));
    }, []);

    const appendMessageToConversation = useCallback((conversationId, message) => {
        updateConversation(conversationId, (conv) => {
            const updatedMessages = [...conv.messages, message].slice(-400);
            return {
                ...conv,
                messages: updatedMessages,
                updatedAt: new Date().toISOString(),
                title: deriveTitle(updatedMessages),
            };
        });
    }, [updateConversation]);

    const appendMessageToActive = useCallback((message) => {
        if (!activeConversation?.id) return;
        appendMessageToConversation(activeConversation.id, message);
    }, [activeConversation, appendMessageToConversation]);

    const createAndSwitchConversation = useCallback(() => {
        const conv = newConversation();
        setConversations((prev) => [conv, ...prev]);
        setActiveConversationId(conv.id);
        pendingConversationIdRef.current = null;
    }, []);

    const clearCurrentConversation = useCallback(() => {
        if (!activeConversation?.id) return;
        updateConversation(activeConversation.id, (conv) => ({
            ...conv,
            messages: [],
            title: 'New conversation',
            updatedAt: new Date().toISOString(),
        }));
    }, [activeConversation, updateConversation]);

    const handleInterrupt = useCallback(() => {
        if (audioState === AUDIO_STATE.PLAYING || assistantState === ASSISTANT_STATES.SPEAKING) {
            stopAudio();
            sendMessage({ type: WS_SEND_TYPES.INTERRUPT });
        }
    }, [audioState, assistantState, stopAudio, sendMessage, AUDIO_STATE]);

    const submitUserText = useCallback((text, type) => {
        const finalText = text.trim();
        if (!finalText) return;

        const now = Date.now();
        if (
            lastUserSubmissionRef.current.text.toLowerCase() === finalText.toLowerCase() &&
            now - lastUserSubmissionRef.current.at < 1200
        ) {
            return;
        }
        lastUserSubmissionRef.current = { text: finalText, at: now };

        unlockAudio();
        if (audioState === AUDIO_STATE.PLAYING || assistantState === ASSISTANT_STATES.SPEAKING) {
            stopAudio();
            sendMessage({ type: WS_SEND_TYPES.INTERRUPT });
        }

        appendMessageToActive({ role: 'user', text: finalText });
        pendingConversationIdRef.current = activeConversation?.id || null;
        sendMessage({ type, text: finalText });
    }, [unlockAudio, audioState, assistantState, stopAudio, sendMessage, appendMessageToActive, activeConversation, AUDIO_STATE]);

    const onCommand = useCallback((text) => {
        submitUserText(text, WS_SEND_TYPES.TRANSCRIPT_FINAL);
    }, [submitUserText]);

    const onSpeechError = useCallback((err) => {
        if (err === 'not-allowed' || err === 'service-not-allowed') {
            setSpeechError('Microphone permission denied. Allow mic access in browser site settings.');
            return;
        }
        if (err === 'network') {
            setSpeechError('Speech recognition network error. Retrying automatically...');
            return;
        }
        if (err === 'no-speech') {
            setSpeechError('No speech detected. Keep talking and Vuddy will retry.');
            return;
        }
        if (err === 'audio-capture') {
            setSpeechError('No microphone detected. Check your input device.');
            return;
        }
        setSpeechError(`Speech recognition error: ${err}`);
    }, []);

    const { isListening, transcript, startListening, stopListening, supported } = useSpeechRecognition({
        onCommand,
        requireWakeWord: false,
        onError: onSpeechError,
    });

    useEffect(() => {
        if (assistantState === ASSISTANT_STATES.SPEAKING && isListening) {
            stopListening();
            sendMessage({ type: WS_SEND_TYPES.STOP_LISTENING });
        }
    }, [assistantState, isListening, stopListening, sendMessage]);

    const toggleListening = () => {
        if (isListening) {
            stopListening();
            sendMessage({ type: WS_SEND_TYPES.STOP_LISTENING });
        } else {
            unlockAudio();
            startListening();
            sendMessage({ type: WS_SEND_TYPES.START_LISTENING });
        }
    };

    const handleSendText = () => {
        if (!textInput.trim()) return;
        submitUserText(textInput, WS_SEND_TYPES.CHAT);
        setTextInput('');
    };

    const handleSuggestion = (text) => {
        submitUserText(text, WS_SEND_TYPES.CHAT);
    };

    useEffect(() => {
        if (!lastMessage) return;

        switch (lastMessage.type) {
            case WS_RECV_TYPES.ASSISTANT_TEXT: {
                const now = Date.now();
                const text = String(lastMessage.text || '');
                if (
                    lastAssistantAppendRef.current.text === text &&
                    now - lastAssistantAppendRef.current.at < 2000
                ) {
                    pendingConversationIdRef.current = null;
                    break;
                }

                const targetId = pendingConversationIdRef.current || activeConversationIdRef.current;
                if (targetId) {
                    appendMessageToConversation(targetId, {
                        role: 'assistant',
                        text: lastMessage.text,
                        tool_results: lastMessage.tool_results,
                    });
                    lastAssistantAppendRef.current = { text, at: now };
                }
                pendingConversationIdRef.current = null;
                break;
            }

            case WS_RECV_TYPES.ASSISTANT_AUDIO_READY:
                if (autoSpeak) {
                    playAudio(lastMessage.audio_url, lastMessage.audio_b64, lastMessage.format);
                }
                break;

            case WS_RECV_TYPES.TOOL_STATUS:
                setToolStatuses((prev) => {
                    const existing = prev.findIndex((t) => t.tool === lastMessage.tool);
                    if (existing >= 0) {
                        const updated = [...prev];
                        updated[existing] = { tool: lastMessage.tool, status: lastMessage.status };
                        return updated;
                    }
                    return [...prev, { tool: lastMessage.tool, status: lastMessage.status }];
                });
                if (lastMessage.status !== 'calling') {
                    setTimeout(() => {
                        setToolStatuses((prev) => prev.filter((t) => t.tool !== lastMessage.tool));
                    }, 3000);
                }
                break;

            default:
                break;
        }
    }, [lastMessage, playAudio, autoSpeak, appendMessageToConversation]);

    useEffect(() => {
        if (conversationRef.current) {
            conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
        }
    }, [messages, activeConversation?.id]);

    const filteredConversations = conversations
        .filter((conv) => {
            const q = historyQuery.trim().toLowerCase();
            if (!q) return true;
            if (conv.title.toLowerCase().includes(q)) return true;
            return conv.messages.some((msg) => String(msg.text || '').toLowerCase().includes(q));
        })
        .sort((a, b) => String(b.updatedAt).localeCompare(String(a.updatedAt)));

    const getStateBarInfo = () => {
        switch (assistantState) {
            case ASSISTANT_STATES.LISTENING:
                return { text: isListening ? 'Listening...' : 'Ready', className: 'assistant-state-bar assistant-state-bar--listening' };
            case ASSISTANT_STATES.THINKING:
                return { text: 'Thinking...', className: 'assistant-state-bar assistant-state-bar--thinking' };
            case ASSISTANT_STATES.SPEAKING:
                return { text: 'Speaking...', className: 'assistant-state-bar assistant-state-bar--speaking' };
            default:
                return { text: isListening ? 'Listening...' : 'Ready', className: 'assistant-state-bar' };
        }
    };
    const stateBar = getStateBarInfo();

    return (
        <div className="home-tab">
            <div className={stateBar.className}>{stateBar.text}</div>

            <div style={{ display: 'grid', gap: '8px', marginTop: '8px' }}>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button className="quick-suggestion-btn" onClick={createAndSwitchConversation}>New Chat</button>
                    <button className="quick-suggestion-btn" onClick={() => setAutoSpeak((prev) => !prev)}>
                        Auto Speak: {autoSpeak ? 'On' : 'Off'}
                    </button>
                    <button className="quick-suggestion-btn" onClick={clearCurrentConversation}>Clear Current Chat</button>
                    <button className="quick-suggestion-btn" onClick={() => setHistoryOpen((prev) => !prev)}>
                        {historyOpen ? 'Hide History' : 'Show History'}
                    </button>
                </div>

                {historyOpen && (
                    <div style={{ display: 'grid', gap: '8px', padding: '8px', background: 'var(--bg-elevated)', borderRadius: '10px' }}>
                        <input
                            type="text"
                            className="text-input"
                            placeholder="Search conversations..."
                            value={historyQuery}
                            onChange={(e) => setHistoryQuery(e.target.value)}
                        />
                        <div style={{ maxHeight: '130px', overflowY: 'auto', display: 'grid', gap: '6px' }}>
                            {filteredConversations.map((conv) => (
                                <button
                                    key={conv.id}
                                    className="quick-suggestion-btn"
                                    onClick={() => {
                                        setActiveConversationId(conv.id);
                                        setHistoryOpen(false);
                                    }}
                                    style={{
                                        textAlign: 'left',
                                        opacity: conv.id === activeConversation?.id ? 1 : 0.8,
                                        border: conv.id === activeConversation?.id ? '1px solid var(--accent-blue)' : undefined,
                                    }}
                                >
                                    {conv.title || 'New conversation'}
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {(!isAudioUnlocked || autoplayBlocked) && (
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
                    <button className="quick-suggestion-btn" onClick={unlockAudio}>Enable Audio</button>
                    {hasPendingAudio && (
                        <button className="quick-suggestion-btn" onClick={playPendingAudio}>Play Last Response</button>
                    )}
                </div>
            )}

            {(audioState === AUDIO_STATE.PLAYING || audioState === AUDIO_STATE.PAUSED) && (
                <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="quick-suggestion-btn" onClick={audioState === AUDIO_STATE.PLAYING ? pauseAudio : resumeAudio}>
                        {audioState === AUDIO_STATE.PLAYING ? 'Pause Voice' : 'Resume Voice'}
                    </button>
                    <button className="quick-suggestion-btn" onClick={handleInterrupt}>Stop Voice</button>
                </div>
            )}

            {toolStatuses.length > 0 && (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {toolStatuses.map((ts) => (
                        <ToolStatusBadge key={ts.tool} tool={ts.tool} status={ts.status} />
                    ))}
                </div>
            )}

            <div className="conversation-area" ref={conversationRef}>
                {messages.length === 0 && (
                    <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 'var(--space-xl)', fontSize: 'var(--font-size-sm)' }}>
                        Tap the mic and just speak, or type a message
                    </div>
                )}
                {messages.map((msg, i) => (
                    <MessageBubble key={i} message={msg} />
                ))}
            </div>

            {isListening && transcript && (
                <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px' }}>
                    Hearing: {transcript}
                </div>
            )}

            {!supported && (
                <div style={{ fontSize: '12px', color: 'var(--accent-coral)', marginTop: '6px' }}>
                    Speech recognition is not supported in this browser. Use Chrome for voice input.
                </div>
            )}

            {speechError && (
                <div style={{ fontSize: '12px', color: 'var(--accent-coral)', marginTop: '6px' }}>
                    {speechError}
                </div>
            )}

            {messages.length === 0 && (
                <div className="quick-suggestions">
                    {QUICK_SUGGESTIONS.map((s) => (
                        <button key={s} className="quick-suggestion-btn" onClick={() => handleSuggestion(s)}>
                            {s}
                        </button>
                    ))}
                </div>
            )}

            <div className="input-area">
                <button
                    className={`mic-button ${isListening ? 'mic-button--listening' : ''}`}
                    onClick={toggleListening}
                    aria-label={isListening ? 'Stop listening' : 'Start listening'}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="9" y="2" width="6" height="11" rx="3" />
                        <path d="M5 10v1a7 7 0 0014 0v-1" />
                        <line x1="12" y1="19" x2="12" y2="23" />
                        <line x1="8" y1="23" x2="16" y2="23" />
                    </svg>
                </button>

                <div className="text-input-wrapper">
                    <input
                        type="text"
                        className="text-input"
                        placeholder="Type a command..."
                        value={textInput}
                        onChange={(e) => setTextInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSendText()}
                    />
                    <button
                        className="send-button"
                        onClick={handleSendText}
                        disabled={!textInput.trim()}
                        aria-label="Send"
                    >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    );
}
