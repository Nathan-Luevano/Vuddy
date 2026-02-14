import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_RECV_TYPES, WS_URL } from '../constants';

export function useWebSocket() {
    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState(null);
    const [llmProvider, setLlmProvider] = useState('ollama');
    const wsRef = useRef(null);
    const reconnectTimeout = useRef(null);
    const reconnectAttempt = useRef(0);
    const mountedRef = useRef(true);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        try {
            const ws = new WebSocket(WS_URL);

            ws.onopen = () => {
                if (!mountedRef.current) return;
                setIsConnected(true);
                reconnectAttempt.current = 0;
            };

            ws.onmessage = (event) => {
                if (!mountedRef.current) return;
                try {
                    const msg = JSON.parse(event.data);
                    setLastMessage(msg);

                    // Extract llm_provider from initial connect message
                    if (msg.type === WS_RECV_TYPES.ASSISTANT_STATE && msg.llm_provider) {
                        setLlmProvider(msg.llm_provider);
                    }
                } catch (e) {
                    console.error('[WS] Failed to parse message:', e);
                }
            };

            ws.onclose = () => {
                if (!mountedRef.current) return;
                setIsConnected(false);
                wsRef.current = null;

                // Exponential backoff reconnect: 1s, 2s, 4s, max 10s
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempt.current), 10000);
                reconnectAttempt.current += 1;
                reconnectTimeout.current = setTimeout(() => {
                    if (mountedRef.current) connect();
                }, delay);
            };

            ws.onerror = (err) => {
                console.error('[WS] Error:', err);
                ws.close();
            };

            wsRef.current = ws;
        } catch (e) {
            console.error('[WS] Connection failed:', e);
        }
    }, []);

    useEffect(() => {
        mountedRef.current = true;
        connect();

        return () => {
            mountedRef.current = false;
            if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
            if (wsRef.current) {
                wsRef.current.onclose = null; // prevent reconnect on unmount
                wsRef.current.close();
            }
        };
    }, [connect]);

    const sendMessage = useCallback((msg) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(msg));
        } else {
            console.warn('[WS] Cannot send, not connected');
        }
    }, []);

    return { sendMessage, lastMessage, isConnected, llmProvider };
}
