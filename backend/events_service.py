"""
Vuddy Backend — Campus Events Service.
Loads seeded events from JSON, filters by time range and tags.
Schema must match shared/events.schema.json.
"""

import json
import os
from datetime import datetime, timedelta
import httpx

EVENTS_DATA_PATH = os.getenv("EVENTS_DATA_PATH", os.path.join("data", "events_seed.json"))
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
EVENTS_CACHE_TTL_SEC = int(os.getenv("EVENTS_CACHE_TTL_SEC", "900"))

_events_cache: list[dict] | None = None
_realtime_cache: dict[str, dict] = {}


def _load_events() -> list[dict]:
    """Load events from seed file. Cached after first load."""
    global _events_cache
    if _events_cache is not None:
        return _events_cache

    try:
        with open(EVENTS_DATA_PATH, "r") as f:
            _events_cache = json.load(f)
    except FileNotFoundError:
        print(f"[EVENTS] Seed file not found at {EVENTS_DATA_PATH}, using empty list")
        _events_cache = []
    except json.JSONDecodeError as e:
        print(f"[EVENTS] Invalid JSON in {EVENTS_DATA_PATH}: {e}")
        _events_cache = []

    return _events_cache


def reload_events() -> None:
    """Force reload events from disk (useful after data changes)."""
    global _events_cache
    _events_cache = None
    _load_events()


def _parse_time_range(time_range: str) -> tuple[datetime, datetime]:
    """
    Parse natural-language time ranges into start/end datetimes.
    'tonight' = 5PM-midnight today
    'tomorrow' = next day 00:00-23:59
    'this weekend' = Saturday + Sunday
    """
    now = datetime.now()
    time_range_lower = time_range.lower().strip()

    if time_range_lower in ("tonight", "this evening"):
        start = now.replace(hour=17, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        return start, end

    if time_range_lower == "tomorrow":
        tomorrow = now + timedelta(days=1)
        start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        end = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)
        return start, end

    if time_range_lower in ("this weekend", "weekend"):
        # Find next Saturday
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.weekday() != 5:
            days_until_saturday = 7
        saturday = now + timedelta(days=days_until_saturday)
        start = saturday.replace(hour=0, minute=0, second=0, microsecond=0)
        sunday = saturday + timedelta(days=1)
        end = sunday.replace(hour=23, minute=59, second=59, microsecond=0)
        return start, end

    if time_range_lower == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)
        return start, end

    # Default: next 24 hours
    return now, now + timedelta(hours=24)


def get_events(time_range: str = "today", tags: list[str] | None = None) -> dict:
    """
    Get campus events filtered by time range and optional tags.
    Returns: {ok: bool, events: [...]}
    """
    try:
        events = _load_events()
        start, end = _parse_time_range(time_range)

        filtered = []
        for event in events:
            try:
                event_start = datetime.fromisoformat(event["start"])
                event_end = datetime.fromisoformat(event["end"])
            except (ValueError, KeyError):
                continue

            # Check time overlap
            if event_end < start or event_start > end:
                continue

            # Check tag filter
            if tags:
                event_tags = set(event.get("tags", []))
                if not event_tags.intersection(set(tags)):
                    continue

            filtered.append({
                "title": event.get("title", ""),
                "start": event.get("start", ""),
                "end": event.get("end", ""),
                "location": event.get("location", ""),
                "tags": event.get("tags", []),
                "description": event.get("description", ""),
            })

        return {"ok": True, "events": filtered}

    except Exception as e:
        print(f"[EVENTS] Error: {e}")
        return {"ok": False, "events": [], "error": str(e)}


async def search_realtime_events(query: str, city: str = "", size: int = 10) -> dict:
    """
    Search real-time events from Ticketmaster Discovery API.
    Falls back to seeded events search when API key isn't configured or on failure.
    """
    query = (query or "").strip()
    if not query:
        return {"ok": False, "events": [], "error": "query is required", "source": "none"}

    size = max(1, min(size, 20))
    cache_key = f"q={query.lower()}|city={city.lower().strip()}|size={size}"
    cached = _get_realtime_cache(cache_key)
    if cached:
        return cached

    if TICKETMASTER_API_KEY:
        params = {
            "apikey": TICKETMASTER_API_KEY,
            "keyword": query,
            "size": size,
            "sort": "date,asc",
        }
        if city.strip():
            params["city"] = city.strip()

        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get(TICKETMASTER_URL, params=params)
            response.raise_for_status()
            data = response.json()
            embedded = data.get("_embedded", {})
            items = embedded.get("events", [])
            result = {
                "ok": True,
                "events": [_normalize_ticketmaster_event(item) for item in items],
                "source": "ticketmaster",
                "live": True,
            }
            _set_realtime_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"[EVENTS] Real-time search failed, using fallback: {e}")

    fallback = _search_seed_events(query=query, city=city, size=size)
    fallback["live"] = False
    _set_realtime_cache(cache_key, fallback)
    return fallback


async def discover_events(city: str = "", size: int = 12) -> dict:
    """
    Curated discovery feed for campus life.
    Uses cache + live provider where configured.
    """
    city = (city or "").strip()
    size = max(1, min(size, 20))
    # Higher-signal query terms for student events.
    query = "campus student university events"
    result = await search_realtime_events(query=query, city=city, size=size)
    if not result.get("ok"):
        return result
    return {
        "ok": True,
        "events": result.get("events", []),
        "source": result.get("source", "unknown"),
        "live": bool(result.get("live")),
        "city": city,
        "cached": True,
        "cache_ttl_sec": EVENTS_CACHE_TTL_SEC,
    }


def _search_seed_events(query: str, city: str = "", size: int = 10) -> dict:
    events = _load_events()
    q = query.lower().strip()
    city_q = city.lower().strip()

    scored = []
    for event in events:
        title = event.get("title", "")
        desc = event.get("description", "")
        location = event.get("location", "")
        tags = " ".join(event.get("tags", []))
        haystack = f"{title} {desc} {location} {tags}".lower()

        if q not in haystack:
            continue
        if city_q and city_q not in location.lower():
            continue

        score = 0
        if q in title.lower():
            score += 3
        if q in tags.lower():
            score += 2
        if q in desc.lower():
            score += 1
        scored.append((score, event))

    scored.sort(key=lambda item: (item[0], item[1].get("start", "")), reverse=True)
    top = [item[1] for item in scored[:size]]
    normalized = [
        {
            "id": evt.get("id", ""),
            "title": evt.get("title", ""),
            "start": evt.get("start", ""),
            "end": evt.get("end", ""),
            "location": evt.get("location", ""),
            "description": evt.get("description", ""),
            "tags": evt.get("tags", []),
            "url": "",
        }
        for evt in top
    ]
    return {"ok": True, "events": normalized, "source": "seed_fallback"}


def _normalize_ticketmaster_event(item: dict) -> dict:
    dates = item.get("dates", {}).get("start", {})
    start = dates.get("dateTime") or dates.get("localDate", "")
    end = item.get("dates", {}).get("end", {}).get("dateTime", "")

    venues = item.get("_embedded", {}).get("venues", [])
    venue_name = venues[0].get("name", "") if venues else ""
    city = venues[0].get("city", {}).get("name", "") if venues else ""
    state = venues[0].get("state", {}).get("stateCode", "") if venues else ""
    location_parts = [part for part in [venue_name, city, state] if part]

    classifications = item.get("classifications", [])
    tags: list[str] = []
    if classifications:
        segment = classifications[0].get("segment", {})
        genre = classifications[0].get("genre", {})
        sub_genre = classifications[0].get("subGenre", {})
        for candidate in (segment.get("name"), genre.get("name"), sub_genre.get("name")):
            if candidate:
                tags.append(candidate)

    return {
        "id": item.get("id", ""),
        "title": item.get("name", ""),
        "start": start,
        "end": end,
        "location": ", ".join(location_parts),
        "description": item.get("info") or item.get("pleaseNote", ""),
        "tags": tags,
        "url": item.get("url", ""),
    }


def _get_realtime_cache(cache_key: str) -> dict | None:
    now = datetime.utcnow().timestamp()
    entry = _realtime_cache.get(cache_key)
    if not entry:
        return None
    if entry.get("expires_at", 0) <= now:
        _realtime_cache.pop(cache_key, None)
        return None
    return entry.get("value")


def _set_realtime_cache(cache_key: str, value: dict) -> None:
    expires_at = datetime.utcnow().timestamp() + EVENTS_CACHE_TTL_SEC
    _realtime_cache[cache_key] = {"expires_at": expires_at, "value": value}
