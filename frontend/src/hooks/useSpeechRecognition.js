import { useState, useRef, useCallback, useEffect } from 'react';
import { WAKE_WORDS } from '../constants';

export function useSpeechRecognition({ onCommand, onWakeWordMiss } = {}) {
    const [isListening, setIsListening] = useState(false);
    const [transcript, setTranscript] = useState('');
    const [supported, setSupported] = useState(true);
    const recognitionRef = useRef(null);
    const restartingRef = useRef(false);

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            setSupported(false);
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            let interimTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    const finalText = result[0].transcript.trim();
                    setTranscript(finalText);

                    // Wake word gating
                    const lower = finalText.toLowerCase();
                    let matched = false;
                    for (const wakeWord of WAKE_WORDS) {
                        if (lower.startsWith(wakeWord)) {
                            const stripped = finalText.substring(wakeWord.length).trim();
                            if (stripped && onCommand) {
                                onCommand(stripped);
                            }
                            matched = true;
                            break;
                        }
                    }

                    if (!matched && onWakeWordMiss) {
                        onWakeWordMiss();
                    }
                } else {
                    interimTranscript += result[0].transcript;
                }
            }
            if (interimTranscript) {
                setTranscript(interimTranscript);
            }
        };

        recognition.onerror = (event) => {
            console.error('[Speech] Error:', event.error);
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                setIsListening(false);
            }
        };

        recognition.onend = () => {
            // Auto-restart if still supposed to be listening
            if (restartingRef.current) {
                try {
                    recognition.start();
                } catch (e) {
                    console.error('[Speech] Restart failed:', e);
                    setIsListening(false);
                    restartingRef.current = false;
                }
            } else {
                setIsListening(false);
            }
        };

        recognitionRef.current = recognition;

        return () => {
            restartingRef.current = false;
            try {
                recognition.stop();
            } catch (e) { /* ignore */ }
        };
    }, [onCommand, onWakeWordMiss]);

    const startListening = useCallback(() => {
        if (!recognitionRef.current) return;
        try {
            restartingRef.current = true;
            recognitionRef.current.start();
            setIsListening(true);
            setTranscript('');
        } catch (e) {
            console.error('[Speech] Start failed:', e);
        }
    }, []);

    const stopListening = useCallback(() => {
        if (!recognitionRef.current) return;
        restartingRef.current = false;
        try {
            recognitionRef.current.stop();
        } catch (e) { /* ignore */ }
        setIsListening(false);
    }, []);

    return { isListening, transcript, startListening, stopListening, supported };
}
