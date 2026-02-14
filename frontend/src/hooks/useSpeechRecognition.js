import { useState, useRef, useCallback, useEffect } from 'react';
import { WAKE_WORDS } from '../constants';

export function useSpeechRecognition({ onCommand, onWakeWordMiss, requireWakeWord = false, onError } = {}) {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [supported, setSupported] = useState(true);
    const recognitionRef = useRef(null);
    const restartingRef = useRef(false);
    const lastFinalRef = useRef('');
    const restartTimerRef = useRef(null);
    const commandCbRef = useRef(onCommand);
    const wakeMissCbRef = useRef(onWakeWordMiss);
    const errorCbRef = useRef(onError);
    const requireWakeWordRef = useRef(requireWakeWord);

    useEffect(() => { commandCbRef.current = onCommand; }, [onCommand]);
    useEffect(() => { wakeMissCbRef.current = onWakeWordMiss; }, [onWakeWordMiss]);
    useEffect(() => { errorCbRef.current = onError; }, [onError]);
    useEffect(() => { requireWakeWordRef.current = requireWakeWord; }, [requireWakeWord]);

    const restartRecognition = useCallback((delayMs = 300) => {
        if (!restartingRef.current || !recognitionRef.current) return;
        if (restartTimerRef.current) clearTimeout(restartTimerRef.current);
        restartTimerRef.current = setTimeout(() => {
            if (!restartingRef.current || !recognitionRef.current) return;
            try {
                recognitionRef.current.start();
                setIsListening(true);
            } catch (e) {
                console.error('[Speech] Restart failed:', e);
            }
        }, delayMs);
    }, []);

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            setSupported(false);
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        recognition.maxAlternatives = 1;

        recognition.onresult = (event) => {
            let interimTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    const finalText = result[0].transcript.trim();
                    if (!finalText || finalText === lastFinalRef.current) continue;
                    lastFinalRef.current = finalText;
                    setTranscript(finalText);

                    if (!requireWakeWordRef.current) {
                        if (commandCbRef.current) commandCbRef.current(finalText);
                        continue;
                    }

                    const lower = finalText.toLowerCase();
                    let matched = false;
                    for (const wakeWord of WAKE_WORDS) {
                        if (!lower.startsWith(wakeWord)) continue;
                        const stripped = finalText.substring(wakeWord.length).trim();
                        if (stripped && commandCbRef.current) commandCbRef.current(stripped);
                        matched = true;
                        break;
                    }

                    if (!matched && wakeMissCbRef.current) {
                        wakeMissCbRef.current();
                    }
                } else {
                    interimTranscript += result[0].transcript;
                }
            }
            if (interimTranscript) setTranscript(interimTranscript);
        };

        recognition.onstart = () => setIsListening(true);

        recognition.onerror = (event) => {
            console.error('[Speech] Error:', event.error);
            if (errorCbRef.current) errorCbRef.current(event.error);

            if (event.error === 'network' || event.error === 'no-speech' || event.error === 'audio-capture') {
                restartRecognition(500);
                return;
            }
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                restartingRef.current = false;
                setIsListening(false);
            }
        };

        recognition.onend = () => {
            if (!restartingRef.current) {
                setIsListening(false);
                return;
            }
            restartRecognition(200);
        };

        recognitionRef.current = recognition;

        return () => {
            restartingRef.current = false;
            if (restartTimerRef.current) {
                clearTimeout(restartTimerRef.current);
                restartTimerRef.current = null;
            }
            try {
                recognition.stop();
            } catch {
                // ignore
            }
        };
    }, [restartRecognition]);

    const startListening = useCallback(() => {
        if (!recognitionRef.current) return;
        try {
            restartingRef.current = true;
            recognitionRef.current.start();
            setIsListening(true);
            setTranscript('');
            lastFinalRef.current = '';
        } catch (e) {
            console.error('[Speech] Start failed:', e);
            if (errorCbRef.current) errorCbRef.current('start-failed');
        }
    }, []);

    const stopListening = useCallback(() => {
        if (!recognitionRef.current) return;
        restartingRef.current = false;
        if (restartTimerRef.current) {
            clearTimeout(restartTimerRef.current);
            restartTimerRef.current = null;
        }
        try {
            recognitionRef.current.stop();
        } catch {
            // ignore
        }
        setIsListening(false);
    }, []);

    return { isListening, transcript, startListening, stopListening, supported };
}
