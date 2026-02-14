import React, { createContext, useContext, useRef } from 'react';

const AudioContextCtx = createContext(null);

export function useAudioContext() {
    return useContext(AudioContextCtx);
}

export function AudioProvider({ children }) {
    const audioContextRef = useRef(null);

    // Initialize lazily (must be after user gesture in WakeScreen)
    if (!audioContextRef.current) {
        try {
            audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
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
