import React, { createContext, useContext, useRef } from 'react';

const AudioContextCtx = createContext(null);

export function useAudioContext() {
    return useContext(AudioContextCtx);
}

export function AudioProvider({ children }) {
    const audioContextRef = useRef(null);

    // Initialize lazily and reuse context unlocked from WakeScreen when available.
    if (!audioContextRef.current) {
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (window.__vuddyAudioCtx) {
                audioContextRef.current = window.__vuddyAudioCtx;
            } else if (Ctx) {
                audioContextRef.current = new Ctx();
            }
        } catch (e) {
            console.warn('[AudioEngine] Could not create AudioContext:', e);
        }
    }

    return (
        <AudioContextCtx.Provider value={audioContextRef}>
            {children}
        </AudioContextCtx.Provider>
    );
}
