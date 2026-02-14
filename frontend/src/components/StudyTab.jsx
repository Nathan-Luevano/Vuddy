import React, { useState, useEffect, useRef } from 'react';

export default function StudyTab() {
    const [topic, setTopic] = useState('');
    const [duration, setDuration] = useState(25);
    const [isActive, setIsActive] = useState(false);
    const [timeRemaining, setTimeRemaining] = useState(0);
    const [sessionTopic, setSessionTopic] = useState('');
    const intervalRef = useRef(null);

    useEffect(() => {
        if (isActive && timeRemaining > 0) {
            intervalRef.current = setInterval(() => {
                setTimeRemaining(prev => {
                    if (prev <= 1) {
                        clearInterval(intervalRef.current);
                        setIsActive(false);
                        return 0;
                    }
                    return prev - 1;
                });
            }, 1000);
        }
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [isActive, timeRemaining]);

    const startSession = () => {
        if (!topic.trim()) return;
        setSessionTopic(topic.trim());
        setTimeRemaining(duration * 60);
        setIsActive(true);
        setTopic('');
    };

    const endSession = () => {
        setIsActive(false);
        setTimeRemaining(0);
        if (intervalRef.current) clearInterval(intervalRef.current);
    };

    const formatTime = (seconds) => {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    };

    const isWarning = isActive && timeRemaining > 0 && timeRemaining < 300; // < 5 min

    return (
        <div className="study-tab">
            <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 700, textAlign: 'center' }}>
                Study Timer
            </h2>

            {/* Timer circle */}
            <div className={`study-timer ${isActive ? 'study-timer--active' : ''} ${isWarning ? 'study-timer--warning' : ''}`}>
                {isActive ? (
                    <>
                        <div className="study-timer__topic">{sessionTopic}</div>
                        <div className="study-timer__time">{formatTime(timeRemaining)}</div>
                    </>
                ) : timeRemaining === 0 && sessionTopic ? (
                    <>
                        <div className="study-timer__topic">Session Complete!</div>
                        <div className="study-timer__time">🎉</div>
                    </>
                ) : (
                    <>
                        <div className="study-timer__topic">Ready to study?</div>
                        <div className="study-timer__time">--:--</div>
                    </>
                )}
            </div>

            {/* Controls */}
            {!isActive ? (
                <div className="study-form">
                    <input
                        type="text"
                        className="study-form__input"
                        placeholder="What are you studying?"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && startSession()}
                    />
                    <div style={{ display: 'flex', gap: 'var(--space-sm)', alignItems: 'center' }}>
                        <label style={{ color: 'var(--text-muted)', fontSize: 'var(--font-size-sm)', flexShrink: 0 }}>
                            Duration:
                        </label>
                        <select
                            className="study-form__input"
                            value={duration}
                            onChange={(e) => setDuration(Number(e.target.value))}
                            style={{ flex: 1 }}
                        >
                            <option value={15}>15 min</option>
                            <option value={25}>25 min</option>
                            <option value={45}>45 min</option>
                            <option value={60}>60 min</option>
                        </select>
                    </div>
                    <button className="study-btn study-btn--start" onClick={startSession}>
                        Start Session
                    </button>
                </div>
            ) : (
                <button className="study-btn study-btn--stop" onClick={endSession}>
                    End Early
                </button>
            )}
        </div>
    );
}
