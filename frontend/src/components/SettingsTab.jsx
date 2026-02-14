import React, { useState } from 'react';
import { useTheme } from '../ThemeContext';

const INTEREST_OPTIONS = [
    'CS', 'Engineering', 'Music', 'Sports', 'Art',
    'Fitness', 'Social', 'Gaming', 'Food', 'Career',
];

const RESPONSE_LENGTHS = ['Short', 'Normal', 'Detailed'];

export default function SettingsTab() {
    const { activeTheme, setActiveTheme: setTheme, themes } = useTheme();
    const [responseLength, setResponseLength] = useState('Normal');
    const [savePrefs, setSavePrefs] = useState(true);
    const [interests, setInterests] = useState(['CS', 'Gaming']);

    const toggleInterest = (interest) => {
        setInterests(prev =>
            prev.includes(interest)
                ? prev.filter(i => i !== interest)
                : [...prev, interest]
        );
    };

    return (
        <div className="settings-tab">
            <h2 className="settings-tab__title">Settings</h2>

            {/* School Theme */}
            <div className="settings-item">
                <div className="settings-item__label">School Theme</div>
                <select
                    className="study-form__input"
                    style={{ width: '100%', marginTop: 'var(--space-xs)' }}
                    value={activeTheme}
                    onChange={(e) => setTheme(e.target.value)}
                >
                    {themes.map((t) => (
                        <option key={t.id} value={t.id}>
                            {t.label}
                        </option>
                    ))}
                </select>
            </div>

            {/* Wake Word */}
            <div className="settings-item">
                <div className="settings-item__label">Wake Word</div>
                <div className="settings-item__value">Hey Vuddy</div>
            </div>

            {/* Voice Response Length */}
            <div className="settings-item">
                <div className="settings-item__label">Voice Response Length</div>
                <div className="segmented-control" style={{ marginTop: 'var(--space-sm)' }}>
                    {RESPONSE_LENGTHS.map((len) => (
                        <button
                            key={len}
                            className={`segmented-control__btn ${responseLength === len ? 'segmented-control__btn--active' : ''}`}
                            onClick={() => setResponseLength(len)}
                        >
                            {len}
                        </button>
                    ))}
                </div>
            </div>

            {/* Privacy */}
            <div className="settings-item settings-toggle">
                <div>
                    <div className="settings-item__label">Privacy</div>
                    <div className="settings-item__value">Save my preferences</div>
                </div>
                <button
                    className={`toggle-switch ${savePrefs ? 'toggle-switch--on' : ''}`}
                    onClick={() => setSavePrefs(!savePrefs)}
                    aria-label="Toggle save preferences"
                />
            </div>

            {/* Interests */}
            <div className="settings-item">
                <div className="settings-item__label">Interests</div>
                <div className="interest-tags" style={{ marginTop: 'var(--space-sm)' }}>
                    {INTEREST_OPTIONS.map((interest) => (
                        <button
                            key={interest}
                            className={`interest-tag ${interests.includes(interest) ? 'interest-tag--active' : ''}`}
                            onClick={() => toggleInterest(interest)}
                        >
                            {interest}
                        </button>
                    ))}
                </div>
            </div>

            {/* About */}
            <div className="settings-about">
                <p style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: 'var(--space-xs)' }}>
                    About Vuddy
                </p>
                <p>Powered by PatriotAI</p>
                <p>Version 1.0.0</p>
            </div>
        </div>
    );
}
