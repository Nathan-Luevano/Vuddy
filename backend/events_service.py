"""
Vuddy Backend — Campus Events Service.
Loads seeded events from JSON, filters by time range and tags.
Schema must match shared/events.schema.json.
"""

import json
import os
from datetime import datetime, timedelta

EVENTS_DATA_PATH = os.getenv("EVENTS_DATA_PATH", os.path.join("data", "events_seed.json"))

_events_cache: list[dict] | None = None


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
