import React, { useState, useEffect } from 'react';
import { API } from '../constants';

const EVENTS_CACHE_KEY = 'vuddy.events.live.cache.v1';
const CACHE_TTL_MS = 10 * 60 * 1000;
const EVENTS_FETCH_SIZE = 100;
const EVENTS_DAYS_AHEAD = 28;

export default function EventsTab() {
    const [events, setEvents] = useState([]);
    const [recommendations, setRecommendations] = useState(null);
    const [loading, setLoading] = useState(true);
    const [loadingRecs, setLoadingRecs] = useState(false);
    const [query, setQuery] = useState('campus events');
    const [schoolCity, setSchoolCity] = useState('');
    const [sourceLabel, setSourceLabel] = useState('');
    const [isLiveSource, setIsLiveSource] = useState(false);

    useEffect(() => {
        loadFromCache();
        initSchoolAndFetch();
    }, []);

    const loadFromCache = () => {
        try {
            const raw = window.localStorage.getItem(EVENTS_CACHE_KEY);
            if (!raw) return;
            const cached = JSON.parse(raw);
            if (!cached?.savedAt || (Date.now() - cached.savedAt) > CACHE_TTL_MS) return;
            setEvents(cached.events || []);
            setQuery(cached.query || 'campus events');
            setSchoolCity(cached.schoolCity || '');
            setSourceLabel(cached.sourceLabel || 'cached');
            setIsLiveSource(Boolean(cached.live));
        } catch {
            // Ignore malformed cache.
        }
    };

    const saveToCache = ({ events: nextEvents, nextQuery, nextSchoolCity, source, live }) => {
        try {
            window.localStorage.setItem(
                EVENTS_CACHE_KEY,
                JSON.stringify({
                    savedAt: Date.now(),
                    events: nextEvents || [],
                    query: nextQuery || '',
                    schoolCity: nextSchoolCity || '',
                    sourceLabel: source || '',
                    live: Boolean(live),
                }),
            );
        } catch {
            // Ignore quota or storage errors.
        }
    };

    const initSchoolAndFetch = async () => {
        try {
            const schoolRes = await fetch(API.SCHOOL);
            const schoolData = await schoolRes.json();
            const city = schoolData?.city || '';
            if (city) {
                setSchoolCity(city);
                await fetchEvents({ discover: true, city, q: query });
                return;
            }
        } catch (e) {
            console.warn('[Events] School lookup failed, using default search:', e);
        }
        await fetchEvents({ discover: true, city: '', q: query });
    };

    const fetchEvents = async ({ discover = false, city = schoolCity, q = query } = {}) => {
        setLoading(true);
        try {
            const endpoint = discover
                ? `${API.EVENTS_DISCOVER}?city=${encodeURIComponent(city || '')}&size=${EVENTS_FETCH_SIZE}&days_ahead=${EVENTS_DAYS_AHEAD}`
                : `${API.EVENTS_SEARCH}?q=${encodeURIComponent(q || 'campus events')}&city=${encodeURIComponent(city || '')}&size=${EVENTS_FETCH_SIZE}&days_ahead=${EVENTS_DAYS_AHEAD}`;
            const res = await fetch(endpoint);
            const data = await res.json();
            if (data.ok) {
                const nextEvents = data.events || [];
                setEvents(nextEvents);
                setSourceLabel(data.source || '');
                setIsLiveSource(Boolean(data.live));
                saveToCache({
                    events: nextEvents,
                    nextQuery: q,
                    nextSchoolCity: city,
                    source: data.source || '',
                    live: data.live,
                });
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
        if (!iso) return '';
        try {
            return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
        } catch {
            return iso;
        }
    };

    const formatDate = (iso) => {
        if (!iso) return '';
        try {
            return new Date(iso).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
        } catch {
            return '';
        }
    };

    const openEvent = (url) => {
        if (!url) return;
        window.open(url, '_blank', 'noopener,noreferrer');
    };

    const openMap = (location) => {
        if (!location) return;
        const mapUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`;
        window.open(mapUrl, '_blank', 'noopener,noreferrer');
    };

    const renderEventCard = (event, reason) => (
        <div className="event-card" key={event.id || event.title}>
            <div className="event-card__title">{event.title}</div>
            {(event.start || event.end) && (
                <div className="event-card__time">
                    {formatDate(event.start)} {event.start ? `· ${formatTime(event.start)}` : ''} {event.end ? `– ${formatTime(event.end)}` : ''}
                </div>
            )}
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
            <div className="event-card__actions">
                {!!event.url && (
                    <button className="event-bubble event-bubble--primary" onClick={() => openEvent(event.url)}>
                        Learn more
                    </button>
                )}
                {!!event.url && (
                    <button className="event-bubble" onClick={() => openEvent(event.url)}>
                        Open source
                    </button>
                )}
                {!!event.location && (
                    <button className="event-bubble" onClick={() => openMap(event.location)}>
                        View map
                    </button>
                )}
            </div>
        </div>
    );

    return (
        <div className="events-tab">
            <div className="events-tab__header">
                <h2 className="events-tab__title">Campus Events</h2>
                <div className="events-tab__meta">
                    {!loading && (
                        <span className="events-source-pill">
                            {events.length} shown · next {EVENTS_DAYS_AHEAD} days
                        </span>
                    )}
                    {sourceLabel && (
                        <span className={`events-source-pill ${isLiveSource ? 'events-source-pill--live' : ''}`}>
                            {isLiveSource ? 'Live' : 'Fallback'}: {sourceLabel}
                        </span>
                    )}
                    <button
                        className="recommend-btn"
                        onClick={fetchRecommendations}
                        disabled={loadingRecs}
                    >
                        {loadingRecs ? 'Loading...' : 'Recommended for me'}
                    </button>
                </div>
            </div>

            <div className="events-search">
                <input
                    className="events-search__input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search real events (clubs, concerts, sports, workshops...)"
                />
                <button className="events-search__btn" onClick={() => fetchEvents({ discover: false, q: query })}>
                    Search
                </button>
                <button className="events-search__btn events-search__btn--secondary" onClick={() => fetchEvents({ discover: true, q: query })}>
                    Refresh
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
                <div className="events-tab__empty">
                    No events found right now. Try broader terms like "student events", "concert", or "club fair".
                </div>
            ) : (
                events.map((evt) => renderEventCard(evt))
            )}
        </div>
    );
}
