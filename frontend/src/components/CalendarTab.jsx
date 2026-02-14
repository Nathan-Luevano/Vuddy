import React, { useState, useEffect } from 'react';
import { API } from '../constants';

const GOOGLE_OAUTH_POPUP_FEATURES = 'width=540,height=760,menubar=no,toolbar=no,status=no';
const CALENDAR_HOURS_AHEAD = 24 * 28;

export default function CalendarTab() {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [title, setTitle] = useState('');
    const [time, setTime] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [syncingGoogle, setSyncingGoogle] = useState(false);
    const [googleStatus, setGoogleStatus] = useState('');

    useEffect(() => {
        fetchCalendar();
    }, []);

    useEffect(() => {
        const onMessage = async (event) => {
            if (event.origin !== window.location.origin) return;
            if (!event.data || event.data.type !== 'google_oauth_code') return;

            if (!event.data.code || !event.data.state) {
                setGoogleStatus('Google sign-in was cancelled or missing required data.');
                setSyncingGoogle(false);
                return;
            }
            await exchangeGoogleCode(event.data.code, event.data.state);
        };

        window.addEventListener('message', onMessage);
        return () => window.removeEventListener('message', onMessage);
    }, []);

    const fetchCalendar = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API.CALENDAR_SUMMARY}?hours_ahead=${CALENDAR_HOURS_AHEAD}`);
            const data = await res.json();
            if (data.ok) {
                setEvents(data.events || []);
            }
        } catch (e) {
            console.error('[Calendar] Fetch failed:', e);
        }
        setLoading(false);
    };

    const handleAddReminder = async () => {
        if (!title.trim() || !time) return;
        setSubmitting(true);
        try {
            const res = await fetch(API.CALENDAR_ADD, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: title.trim(),
                    time_iso: new Date(time).toISOString(),
                    notes: '',
                }),
            });
            const data = await res.json();
            if (data.ok) {
                setShowModal(false);
                setTitle('');
                setTime('');
                fetchCalendar();
            }
        } catch (e) {
            console.error('[Calendar] Add failed:', e);
        }
        setSubmitting(false);
    };

    const connectGoogleCalendar = async () => {
        setSyncingGoogle(true);
        setGoogleStatus('');
        const redirectUri = `${window.location.origin}/google-calendar-callback.html`;
        try {
            const res = await fetch(`${API.CALENDAR_GOOGLE_AUTH_URL}?redirect_uri=${encodeURIComponent(redirectUri)}`);
            const data = await res.json();
            if (!data.ok || !data.auth_url) {
                setGoogleStatus(data.error || 'Unable to start Google sign-in.');
                setSyncingGoogle(false);
                return;
            }

            const popup = window.open(data.auth_url, 'vuddy-google-oauth', GOOGLE_OAUTH_POPUP_FEATURES);
            if (!popup) {
                setGoogleStatus('Popup blocked. Please allow popups and try again.');
                setSyncingGoogle(false);
                return;
            }
        } catch (e) {
            console.error('[Calendar] Google auth URL failed:', e);
            setGoogleStatus('Could not reach Google auth endpoint.');
            setSyncingGoogle(false);
        }
    };

    const exchangeGoogleCode = async (code, state) => {
        const redirectUri = `${window.location.origin}/google-calendar-callback.html`;
        try {
            const res = await fetch(API.CALENDAR_GOOGLE_EXCHANGE, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    code,
                    state,
                    redirect_uri: redirectUri,
                    calendar_id: 'primary',
                    max_results: 50,
                }),
            });
            const data = await res.json();
            if (!data.ok) {
                setGoogleStatus(data.error || 'Google calendar sync failed.');
                setSyncingGoogle(false);
                return;
            }
            setGoogleStatus(`Google calendar connected. Imported ${data.imported || 0} event(s).`);
            await fetchCalendar();
        } catch (e) {
            console.error('[Calendar] Google code exchange failed:', e);
            setGoogleStatus('Google calendar sync failed.');
        }
        setSyncingGoogle(false);
    };

    const formatTime = (iso) => {
        try {
            return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        } catch {
            return iso;
        }
    };

    const formatDate = (iso) => {
        try {
            return new Date(iso).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
        } catch {
            return '';
        }
    };

    return (
        <div className="calendar-tab">
            <div className="calendar-tab__header">
                <h2 className="calendar-tab__title">My Calendar</h2>
                <div className="calendar-tab__actions">
                    <button
                        className="google-connect-btn"
                        onClick={connectGoogleCalendar}
                        disabled={syncingGoogle}
                    >
                        {syncingGoogle ? 'Connecting...' : 'Connect Google'}
                    </button>
                    <button
                        className="add-reminder-btn"
                        onClick={() => setShowModal(true)}
                    >
                        + Add Reminder
                    </button>
                </div>
            </div>
            {googleStatus && (
                <div className="calendar-google-status">{googleStatus}</div>
            )}

            {loading ? (
                <div className="loading-spinner" />
            ) : events.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 'var(--space-xl)' }}>
                    No upcoming events. Add a reminder!
                </div>
            ) : (
                events.map((evt, i) => (
                    <div className="calendar-event" key={evt.id || i}>
                        <div className="calendar-event__dot" />
                        <div className="calendar-event__info">
                            <div className="calendar-event__title">{evt.title}</div>
                            <div className="calendar-event__time">
                                {formatDate(evt.start)} · {formatTime(evt.start)}
                                {evt.end && ` – ${formatTime(evt.end)}`}
                            </div>
                        </div>
                    </div>
                ))
            )}

            {/* Add Reminder Modal */}
            {showModal && (
                <div className="modal-overlay" onClick={() => setShowModal(false)}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <h3 className="modal__title">Add Reminder</h3>
                        <input
                            type="text"
                            className="modal__input"
                            placeholder="Reminder title"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                        />
                        <input
                            type="datetime-local"
                            className="modal__input"
                            value={time}
                            onChange={(e) => setTime(e.target.value)}
                        />
                        <div className="modal__actions">
                            <button
                                className="modal__btn modal__btn--cancel"
                                onClick={() => setShowModal(false)}
                            >
                                Cancel
                            </button>
                            <button
                                className="modal__btn modal__btn--submit"
                                onClick={handleAddReminder}
                                disabled={submitting || !title.trim() || !time}
                            >
                                {submitting ? 'Adding...' : 'Add'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
