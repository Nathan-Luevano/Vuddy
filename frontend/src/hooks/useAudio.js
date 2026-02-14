import { useState, useRef, useCallback } from 'react';

const AUDIO_STATE = {
    IDLE: 'idle',
    LOADING: 'loading',
    PLAYING: 'playing',
};

export function useAudio(audioContextRef) {
    const [audioState, setAudioState] = useState(AUDIO_STATE.IDLE);
    const sourceRef = useRef(null);

    const stopAudio = useCallback(() => {
        if (sourceRef.current) {
            try {
                sourceRef.current.stop();
            } catch (e) { /* already stopped */ }
            sourceRef.current = null;
        }
        setAudioState(AUDIO_STATE.IDLE);
    }, []);

    const playAudio = useCallback(async (audioUrl, audioB64, format) => {
        const ctx = audioContextRef?.current;
        if (!ctx) {
            console.warn('[Audio] No AudioContext available');
            return;
        }

        // Stop any current playback
        stopAudio();

        setAudioState(AUDIO_STATE.LOADING);

        try {
            let arrayBuffer;

            if (audioB64) {
                // Decode base64 audio
                const binary = atob(audioB64);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) {
                    bytes[i] = binary.charCodeAt(i);
                }
                arrayBuffer = bytes.buffer;
            } else if (audioUrl) {
                // Fetch audio from URL
                const response = await fetch(audioUrl);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                arrayBuffer = await response.arrayBuffer();
            } else {
                console.warn('[Audio] No audio source provided');
                setAudioState(AUDIO_STATE.IDLE);
                return;
            }

            const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(ctx.destination);

            source.onended = () => {
                sourceRef.current = null;
                setAudioState(AUDIO_STATE.IDLE);
            };

            sourceRef.current = source;
            source.start(0);
            setAudioState(AUDIO_STATE.PLAYING);
        } catch (e) {
            console.error('[Audio] Playback failed:', e);
            setAudioState(AUDIO_STATE.IDLE);
        }
    }, [audioContextRef, stopAudio]);

    return { audioState, playAudio, stopAudio, AUDIO_STATE };
}
