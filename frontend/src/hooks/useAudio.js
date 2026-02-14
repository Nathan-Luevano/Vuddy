import { useState, useRef, useCallback } from 'react';

const AUDIO_STATE = {
    IDLE: 'idle',
    LOADING: 'loading',
    PLAYING: 'playing',
    PAUSED: 'paused',
};

function resolveAudioUrls(src) {
    if (!src) return [];
    if (src.startsWith('blob:')) return [src];

    const urls = [];
    const backendOriginFromEnv = (import.meta?.env?.VITE_BACKEND_ORIGIN || '').trim();
    if (backendOriginFromEnv) {
        const clean = backendOriginFromEnv.replace(/\/$/, '');
        if (src.startsWith('http://') || src.startsWith('https://')) {
            const parsed = new URL(src);
            urls.push(`${clean}${parsed.pathname}`);
        } else if (src.startsWith('/')) {
            urls.push(`${clean}${src}`);
        }
    }

    const isAbsoluteHttp = src.startsWith('http://') || src.startsWith('https://');
    const parsed = isAbsoluteHttp ? new URL(src) : null;
    const path = parsed ? parsed.pathname : src;

    // Strong preference: route TTS media to backend :8000 in dev/LAN.
    if (path && path.startsWith('/api/audio/tts/')) {
        urls.push(`${window.location.protocol}//${window.location.hostname}:8000${path}`);
    }

    if (isAbsoluteHttp) {
        urls.push(src);
    } else if (src.startsWith('/')) {
        // Same-origin proxy fallback.
        urls.push(`${window.location.origin}${src}`);
        // Direct backend fallback.
        urls.push(`${window.location.protocol}//${window.location.hostname}:8000${src}`);
    } else {
        urls.push(src);
    }

    return [...new Set(urls)];
}

export function useAudio(audioContextRef) {
    const [audioState, setAudioState] = useState(AUDIO_STATE.IDLE);
    const [isAudioUnlocked, setIsAudioUnlocked] = useState(() => {
        try {
            return window.localStorage.getItem('vuddy_audio_unlocked') === 'true';
        } catch {
            return false;
        }
    });
    const [autoplayBlocked, setAutoplayBlocked] = useState(false);
    const [lastAudioError, setLastAudioError] = useState('');
    const [lastAudioEvent, setLastAudioEvent] = useState('');
    const [lastAudioUrl, setLastAudioUrl] = useState('');
    const audioElRef = useRef(null);
    const objectUrlRef = useRef(null);
    const playbackTokenRef = useRef(0);
    const pendingAudioRef = useRef(null);

    const cleanupObjectUrl = useCallback(() => {
        if (objectUrlRef.current) {
            URL.revokeObjectURL(objectUrlRef.current);
            objectUrlRef.current = null;
        }
    }, []);

    const getOrCreateAudioEl = useCallback(() => {
        if (!audioElRef.current) {
            const el = new Audio();
            el.preload = 'auto';
            el.playsInline = true;
            el.onplay = () => setLastAudioEvent('play');
            el.onpause = () => setLastAudioEvent('pause');
            el.onwaiting = () => setLastAudioEvent('waiting');
            el.onstalled = () => setLastAudioEvent('stalled');
            el.onerror = () => {
                const code = el.error?.code ?? 'unknown';
                const msg = `[Audio] media error code=${code}`;
                console.error(msg, el.error);
                setLastAudioError(msg);
                setLastAudioEvent('error');
            };
            audioElRef.current = el;
        }
        return audioElRef.current;
    }, []);

    const stopAudio = useCallback(() => {
        playbackTokenRef.current += 1;
        if (audioElRef.current) {
            audioElRef.current.pause();
            audioElRef.current.src = '';
            audioElRef.current.onended = null;
        }
        cleanupObjectUrl();
        setAudioState(AUDIO_STATE.IDLE);
    }, [cleanupObjectUrl]);

    const unlockAudio = useCallback(async () => {
        try {
            const ctx = audioContextRef?.current;
            if (ctx && ctx.state !== 'running') {
                await ctx.resume();
            }
        } catch (e) {
            console.warn('[Audio] AudioContext resume failed:', e);
        }

        try {
            const el = getOrCreateAudioEl();
            const silentDataUri = 'data:audio/mp3;base64,SUQzAwAAAAAAI1RTU0UAAAAPAAADTGF2ZjU2LjE0LjEwNAAAAAAAAAAAAAAA//uQxAADBzQAOwAABpAAAACAAADSAAAAETGF2YzU2LjE4AAAAAAAAAAAAAAAAJAAAAAAAAAAAAAAAAAAAA//uQxAADwAAA';
            const prevSrc = el.src;
            const prevMuted = el.muted;
            const prevVolume = el.volume;
            el.muted = true;
            el.volume = 0;
            el.src = silentDataUri;
            await el.play();
            el.pause();
            el.currentTime = 0;
            el.src = prevSrc || '';
            el.muted = prevMuted;
            el.volume = prevVolume;
        } catch (e) {
            console.warn('[Audio] Media element unlock failed:', e);
        }

        try {
            window.localStorage.setItem('vuddy_audio_unlocked', 'true');
        } catch {
            // ignore
        }
        setIsAudioUnlocked(true);
        setAutoplayBlocked(false);
    }, [audioContextRef, getOrCreateAudioEl]);

    const pauseAudio = useCallback(() => {
        const el = audioElRef.current;
        if (el && !el.paused) {
            el.pause();
            setAudioState(AUDIO_STATE.PAUSED);
        }
    }, []);

    const resumeAudio = useCallback(async () => {
        const el = audioElRef.current;
        if (!el || !el.paused) return;
        try {
            await el.play();
            setAudioState(AUDIO_STATE.PLAYING);
        } catch (e) {
            console.error('[Audio] Resume failed:', e);
            setAudioState(AUDIO_STATE.IDLE);
        }
    }, []);

    const playAudio = useCallback(async (audioUrl, audioB64, format) => {
        stopAudio();
        const token = playbackTokenRef.current;
        setAudioState(AUDIO_STATE.LOADING);
        setLastAudioError('');
        setLastAudioEvent('loading');
        pendingAudioRef.current = { audioUrl, audioB64, format };

        try {
            let src = audioUrl;
            if (audioB64) {
                const binary = atob(audioB64);
                const bytes = new Uint8Array(binary.length);
                for (let i = 0; i < binary.length; i++) {
                    bytes[i] = binary.charCodeAt(i);
                }
                const mimeType = format === 'wav' ? 'audio/wav' : 'audio/mpeg';
                const blob = new Blob([bytes], { type: mimeType });
                src = URL.createObjectURL(blob);
                objectUrlRef.current = src;
            }

            if (!src) {
                setAudioState(AUDIO_STATE.IDLE);
                return;
            }

            const audioEl = getOrCreateAudioEl();
            const candidates = audioB64 ? [src] : resolveAudioUrls(src);
            let lastError = null;

            for (const candidate of candidates) {
                try {
                    setLastAudioUrl(candidate);
                    audioEl.src = candidate;
                    audioEl.onended = () => {
                        if (playbackTokenRef.current !== token) return;
                        cleanupObjectUrl();
                        setAudioState(AUDIO_STATE.IDLE);
                    };
                    await audioEl.play();
                    if (playbackTokenRef.current !== token) {
                        audioEl.pause();
                        return;
                    }
                    setAutoplayBlocked(false);
                    setAudioState(AUDIO_STATE.PLAYING);
                    return;
                } catch (err) {
                    lastError = err;
                    console.warn(`[Audio] Candidate failed: ${candidate}`, err);
                }
            }
            throw lastError || new Error('No playable audio source');
        } catch (e) {
            console.error('[Audio] Playback failed:', e);
            const errMsg = `[Audio] Playback failed: ${e?.name || 'Error'} ${e?.message || ''}`.trim();
            setLastAudioError(errMsg);
            setLastAudioEvent('playback-failed');
            cleanupObjectUrl();
            if (e?.name === 'NotAllowedError' || e?.name === 'AbortError') {
                setAutoplayBlocked(true);
            }
            setAudioState(AUDIO_STATE.IDLE);
        }
    }, [stopAudio, cleanupObjectUrl, getOrCreateAudioEl]);

    const playPendingAudio = useCallback(async () => {
        if (!pendingAudioRef.current) return;
        await unlockAudio();
        const { audioUrl, audioB64, format } = pendingAudioRef.current;
        await playAudio(audioUrl, audioB64, format);
    }, [unlockAudio, playAudio]);

    return {
        audioState,
        playAudio,
        stopAudio,
        pauseAudio,
        resumeAudio,
        unlockAudio,
        playPendingAudio,
        isAudioUnlocked,
        autoplayBlocked,
        hasPendingAudio: !!pendingAudioRef.current,
        lastAudioError,
        lastAudioEvent,
        lastAudioUrl,
        AUDIO_STATE,
    };
}
