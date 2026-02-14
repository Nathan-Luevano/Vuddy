import React, { useState, useEffect } from 'react';
import { API } from '../constants';

export default function EventsTab() {
    const [events, setEvents] = useState([]);
    const [recommendations, setRecommendations] = useState(null);
    const [loading, setLoading] = useState(true);
    const [loadingRecs, setLoadingRecs] = useState(false);

    useEffect(() => {
        fetchEvents();
    }, []);

    const fetchEvents = async () => {
        setLoading(true);
        try {
            const res = await fetch(API.EVENTS);
            const data = await res.json();
            if (data.ok) {
                setEvents(data.events || []);
            }
        } catch (e) {
            console.error('[Events] Fetch failed:', e);
        }
        setLoading(false);
    };

    const fetchRecommendations = async () => {
        setLoadingRecs(true);
        try {
            const res = await fetch(API.EVENTS_RECOMMENDATIONS);
            const data = await res.json();
            if (data.ok) {
                setRecommendations({
                    events: data.events || [],
                    reasons: data.reasons || [],
                });
            }
        } catch (e) {
            console.error('[Events] Recommendations fetch failed:', e);
        }
        setLoadingRecs(false);
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

    const renderEventCard = (event, reason) => (
        <div className="event-card" key={event.id || event.title}>
            <div className="event-card__title">{event.title}</div>
            <div className="event-card__time">
                {formatDate(event.start)} · {formatTime(event.start)} – {formatTime(event.end)}
            </div>
            <div className="event-card__location">{event.location}</div>
            {event.description && (
                <div className="event-card__description">{event.description}</div>
            )}
            {event.tags && (
                <div className="event-card__tags">
                    {event.tags.map((tag) => (
                        <span key={tag} className="tag-pill">{tag}</span>
                    ))}
                </div>
            )}
            {reason && (
                <div className="event-card__reason">💡 {reason}</div>
            )}
        </div>
    );

    return (
        <div className="events-tab">
            <div className="events-tab__header">
                <h2 className="events-tab__title">Campus Events</h2>
                <button
                    className="recommend-btn"
                    onClick={fetchRecommendations}
                    disabled={loadingRecs}
                >
                    {loadingRecs ? 'Loading...' : 'Recommended for me'}
                </button>
            </div>

            {/* Recommendations section */}
            {recommendations && (
                <>
                    <h3 style={{ fontSize: 'var(--font-size-sm)', color: 'var(--accent-teal)', fontWeight: 600 }}>
                        ✨ Recommended for You
                    </h3>
                    {recommendations.events.map((evt, i) =>
                        renderEventCard(evt, recommendations.reasons?.[i])
                    )}
                    <hr style={{ border: 'none', borderTop: '1px solid var(--bg-elevated)', margin: 'var(--space-sm) 0' }} />
                </>
            )}

            {/* All events */}
            {loading ? (
                <div className="loading-spinner" />
            ) : events.length === 0 ? (
                <div className="events-tab__empty">No events available right now.</div>
            ) : (
                events.map((evt) => renderEventCard(evt))
            )}
        </div>
    );
}
