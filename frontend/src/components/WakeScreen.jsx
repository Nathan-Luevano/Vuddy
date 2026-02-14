import React, { useState } from 'react';

export default function WakeScreen({ onWake }) {
    const [fading, setFading] = useState(false);

    const handleTap = async () => {
        try {
            const Ctx = window.AudioContext || window.webkitAudioContext;
            if (Ctx) {
                const ctx = window.__vuddyAudioCtx || new Ctx();
                await ctx.resume();
                window.__vuddyAudioCtx = ctx;
            }
        } catch (e) {
            console.warn('[WakeScreen] AudioContext init failed:', e);
        }

        setFading(true);
        setTimeout(() => {
            onWake();
        }, 300);
    };

    return (
        <div
            className={`wake-screen ${fading ? 'fading' : ''}`}
            onClick={handleTap}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && handleTap()}
        >
            <svg className="wake-screen__icon" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="32" cy="32" r="30" fill="#162544" stroke="#4A90D9" strokeWidth="2" />
                <rect x="26" y="16" width="12" height="22" rx="6" fill="#4A90D9" />
                <path d="M20 32v4a12 12 0 0024 0v-4" stroke="#4A90D9" strokeWidth="2.5" strokeLinecap="round" />
                <line x1="32" y1="48" x2="32" y2="54" stroke="#4A90D9" strokeWidth="2.5" strokeLinecap="round" />
                <line x1="24" y1="54" x2="40" y2="54" stroke="#4A90D9" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <div className="wake-screen__title">Tap to start Vuddy</div>
            <div className="wake-screen__subtitle">Your campus desk buddy</div>
        </div>
    );
}
