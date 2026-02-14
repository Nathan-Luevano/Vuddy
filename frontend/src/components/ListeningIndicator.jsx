import React from 'react';
import { ASSISTANT_STATES } from '../constants';

export default function ListeningIndicator({ state }) {
    const renderVisual = () => {
        switch (state) {
            case ASSISTANT_STATES.LISTENING:
                return (
                    <div className="sound-waves">
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                    </div>
                );
            case ASSISTANT_STATES.THINKING:
                return (
                    <div className="listening-indicator listening-indicator--thinking">
                        <div className="listening-indicator__dots">
                            <div className="listening-indicator__dot" />
                            <div className="listening-indicator__dot" />
                            <div className="listening-indicator__dot" />
                        </div>
                    </div>
                );
            case ASSISTANT_STATES.SPEAKING:
                return (
                    <div className="sound-waves">
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                        <div className="sound-wave-bar" />
                    </div>
                );
            default:
                return null;
        }
    };

    const getLabel = () => {
        switch (state) {
            case ASSISTANT_STATES.IDLE: return 'Tap to start';
            case ASSISTANT_STATES.LISTENING: return "Listening... say 'Hey Vuddy'";
            case ASSISTANT_STATES.THINKING: return 'Thinking...';
            case ASSISTANT_STATES.SPEAKING: return 'Speaking...';
            default: return '';
        }
    };

    return (
        <div className="listening-indicator">
            {renderVisual()}
            <div className="listening-indicator__label">{getLabel()}</div>
        </div>
    );
}
