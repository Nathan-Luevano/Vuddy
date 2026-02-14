"""
Vuddy Backend — Calendar Service.
Loads from data/fixtures/calendar.json as default.
Optional Google Calendar API (Phase 2).
"""

import json
import os
import uuid
from datetime import datetime, timedelta

CALENDAR_FILE = os.path.join("data", "fixtures", "calendar.json")

_calendar_cache: list[dict] | None = None


def _load_calendar() -> list[dict]:
    """Load calendar events from fixture file. Cached after first load."""
    global _calendar_cache
    if _calendar_cache is not None:
        return _calendar_cache

    try:
        with open(CALENDAR_FILE, "r") as f:
            _calendar_cache = json.load(f)
    except FileNotFoundError:
        print(f"[CALENDAR] Fixture file not found at {CALENDAR_FILE}, using empty list")
        _calendar_cache = []
    except json.JSONDecodeError as e:
        print(f"[CALENDAR] Invalid JSON in {CALENDAR_FILE}: {e}")
        _calendar_cache = []

    return _calendar_cache


def _save_calendar(events: list[dict]) -> None:
    """Persist calendar events to the fixture file."""
    global _calendar_cache
    _calendar_cache = events
    os.makedirs(os.path.dirname(CALENDAR_FILE), exist_ok=True)
    with open(CALENDAR_FILE, "w") as f:
        json.dump(events, f, indent=2)


def get_summary(hours_ahead: int = 24) -> dict:
    """
    Get upcoming calendar events within the next N hours.
    Returns: {ok: bool, events: [{title, start, end}]}
    """
    try:
        events = _load_calendar()
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)

        upcoming = []
        for event in events:
            try:
                event_start = datetime.fromisoformat(event["start"])
            except (ValueError, KeyError):
                continue

            if now <= event_start <= cutoff:
                upcoming.append({
                    "title": event.get("title", ""),
                    "start": event.get("start", ""),
                    "end": event.get("end", ""),
                })

        # Sort by start time
        upcoming.sort(key=lambda e: e["start"])

        return {"ok": True, "events": upcoming}

    except Exception as e:
        print(f"[CALENDAR] Error: {e}")
        return {"ok": False, "events": [], "error": str(e)}


def add_item(title: str, time_iso: str, notes: str = "") -> dict:
    """
    Add a new event/reminder to the local calendar store.
    Returns: {ok: bool, id: str}
    """
    try:
        events = _load_calendar()
        event_id = f"cal_{uuid.uuid4().hex[:8]}"

        # Default end time: 1 hour after start
        try:
            start_dt = datetime.fromisoformat(time_iso)
            end_dt = start_dt + timedelta(hours=1)
            end_iso = end_dt.isoformat()
        except ValueError:
            end_iso = time_iso

        new_event = {
            "id": event_id,
            "title": title,
            "start": time_iso,
            "end": end_iso,
            "notes": notes,
        }

        events.append(new_event)
        _save_calendar(events)

        return {"ok": True, "id": event_id}

    except Exception as e:
        print(f"[CALENDAR] Error adding item: {e}")
        return {"ok": False, "error": str(e)}
