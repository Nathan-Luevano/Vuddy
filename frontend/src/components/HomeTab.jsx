import React, { useState, useRef, useEffect, useCallback } from 'react';
import { ASSISTANT_STATES, WS_SEND_TYPES, WS_RECV_TYPES, QUICK_SUGGESTIONS } from '../constants';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { useAudio } from '../hooks/useAudio';
import { useAudioContext } from '../AudioEngine';
import MessageBubble from './MessageBubble';
import ToolStatusBadge from './ToolStatusBadge';

export default function HomeTab({ sendMessage, lastMessage, assistantState }) {
    const [messages, setMessages] = useState([]);
    const [textInput, setTextInput] = useState('');
    const [wakeHint, setWakeHint] = useState(false);
    const [toolStatuses, setToolStatuses] = useState([]);
    const conversationRef = useRef(null);
    const audioContextRef = useAudioContext();
    const { audioState, playAudio, stopAudio, AUDIO_STATE } = useAudio(audioContextRef);

    // Handle interrupt: stop audio + send interrupt message
    const handleInterrupt = useCallback(() => {
        if (audioState === AUDIO_STATE.PLAYING || assistantState === ASSISTANT_STATES.SPEAKING) {
            stopAudio();
            sendMessage({ type: WS_SEND_TYPES.INTERRUPT });
        }
    }, [audioState, assistantState, stopAudio, sendMessage, AUDIO_STATE]);

    // Speech recognition with wake word gating
    const onCommand = useCallback((text) => {
        // Interrupt if currently speaking
        if (audioState === AUDIO_STATE.PLAYING || assistantState === ASSISTANT_STATES.SPEAKING) {
            stopAudio();
            sendMessage({ type: WS_SEND_TYPES.INTERRUPT });
        }

        setMessages(prev => [...prev, { role: 'user', text }]);
        sendMessage({ type: WS_SEND_TYPES.TRANSCRIPT_FINAL, text });
        setWakeHint(false);
    }, [sendMessage, audioState, assistantState, stopAudio, AUDIO_STATE]);

    const onWakeWordMiss = useCallback(() => {
        setWakeHint(true);
        setTimeout(() => setWakeHint(false), 2500);
    }, []);

    const { isListening, transcript, startListening, stopListening, supported } = useSpeechRecognition({
        onCommand,
        onWakeWordMiss,
    });

    // Toggle listening
    const toggleListening = () => {
        if (isListening) {
            stopListening();
            sendMessage({ type: WS_SEND_TYPES.STOP_LISTENING });
        } else {
            startListening();
            sendMessage({ type: WS_SEND_TYPES.START_LISTENING });
        }
    };

    // Handle typed input
    const handleSendText = () => {
        const text = textInput.trim();
        if (!text) return;

        // Interrupt if playing
        if (audioState === AUDIO_STATE.PLAYING || assistantState === ASSISTANT_STATES.SPEAKING) {
            stopAudio();
            sendMessage({ type: WS_SEND_TYPES.INTERRUPT });
        }

        setMessages(prev => [...prev, { role: 'user', text }]);
        sendMessage({ type: WS_SEND_TYPES.CHAT, text });
        setTextInput('');
    };

    // Handle quick suggestion
    const handleSuggestion = (text) => {
        if (audioState === AUDIO_STATE.PLAYING || assistantState === ASSISTANT_STATES.SPEAKING) {
            stopAudio();
            sendMessage({ type: WS_SEND_TYPES.INTERRUPT });
        }
        setMessages(prev => [...prev, { role: 'user', text }]);
        sendMessage({ type: WS_SEND_TYPES.CHAT, text });
    };

    // Process incoming WS messages
    useEffect(() => {
        if (!lastMessage) return;

        switch (lastMessage.type) {
            case WS_RECV_TYPES.ASSISTANT_TEXT:
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    text: lastMessage.text,
                    tool_results: lastMessage.tool_results,
                }]);
                break;

            case WS_RECV_TYPES.ASSISTANT_AUDIO_READY:
                playAudio(lastMessage.audio_url, lastMessage.audio_b64, lastMessage.format);
                break;

            case WS_RECV_TYPES.TOOL_STATUS:
                setToolStatuses(prev => {
                    const existing = prev.findIndex(t => t.tool === lastMessage.tool);
                    if (existing >= 0) {
                        const updated = [...prev];
                        updated[existing] = { tool: lastMessage.tool, status: lastMessage.status };
                        return updated;
                    }
                    return [...prev, { tool: lastMessage.tool, status: lastMessage.status }];
                });
                // Clear done/error statuses after 3s
                if (lastMessage.status !== 'calling') {
                    setTimeout(() => {
                        setToolStatuses(prev => prev.filter(t => t.tool !== lastMessage.tool));
                    }, 3000);
                }
                break;

            default:
                break;
        }
    }, [lastMessage, playAudio]);

    // Auto-scroll conversation
    useEffect(() => {
        if (conversationRef.current) {
            conversationRef.current.scrollTop = conversationRef.current.scrollHeight;
        }
    }, [messages]);

    // Get state bar text and class
    const getStateBarInfo = () => {
        switch (assistantState) {
            case ASSISTANT_STATES.LISTENING:
                return { text: isListening ? "Listening... say 'Hey Vuddy'" : 'Ready', className: 'assistant-state-bar assistant-state-bar--listening' };
            case ASSISTANT_STATES.THINKING:
                return { text: 'Thinking...', className: 'assistant-state-bar assistant-state-bar--thinking' };
            case ASSISTANT_STATES.SPEAKING:
                return { text: 'Speaking...', className: 'assistant-state-bar assistant-state-bar--speaking' };
            default:
                return { text: isListening ? "Listening... say 'Hey Vuddy'" : 'Ready', className: 'assistant-state-bar' };
        }
    };

    const stateBar = getStateBarInfo();

    return (
        <div className="home-tab">
            {/* State bar */}
            <div className={stateBar.className}>
                {stateBar.text}
            </div>

            {/* Tool statuses */}
            {toolStatuses.length > 0 && (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {toolStatuses.map((ts) => (
                        <ToolStatusBadge key={ts.tool} tool={ts.tool} status={ts.status} />
                    ))}
                </div>
            )}

            {/* Conversation area */}
            <div className="conversation-area" ref={conversationRef}>
                {messages.length === 0 && (
                    <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 'var(--space-xl)', fontSize: 'var(--font-size-sm)' }}>
                        Say "Hey Vuddy" or type a message to get started
                    </div>
                )}
                {messages.slice(-10).map((msg, i) => (
                    <MessageBubble key={i} message={msg} />
                ))}
            </div>

            {/* Wake word hint */}
            {wakeHint && (
                <div className="wake-hint">Say "Hey Vuddy" first</div>
            )}

            {/* Quick suggestions */}
            {messages.length === 0 && (
                <div className="quick-suggestions">
                    {QUICK_SUGGESTIONS.map((s) => (
                        <button
                            key={s}
                            className="quick-suggestion-btn"
                            onClick={() => handleSuggestion(s)}
                        >
                            {s}
                        </button>
                    ))}
                </div>
            )}

            {/* Input area */}
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
