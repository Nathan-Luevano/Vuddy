import React, { useState, useEffect } from 'react';
import { API } from '../constants';

export default function CalendarTab() {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [title, setTitle] = useState('');
    const [time, setTime] = useState('');
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        fetchCalendar();
    }, []);

    const fetchCalendar = async () => {
        setLoading(true);
        try {
            const res = await fetch(API.CALENDAR_SUMMARY);
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
                <button
                    className="add-reminder-btn"
                    onClick={() => setShowModal(true)}
                >
                    + Add Reminder
                </button>
            </div>

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
