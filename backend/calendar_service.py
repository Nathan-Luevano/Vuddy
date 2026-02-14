"""
Vuddy Backend — Calendar Service.
Loads from data/fixtures/calendar.json as default.
Optional Google Calendar API (Phase 2).
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote
import httpx

CALENDAR_FILE = os.getenv("CALENDAR_FILE", os.path.join("data", "calendar.json"))
GOOGLE_CALENDAR_API_KEY = os.getenv("GOOGLE_CALENDAR_API_KEY", "")

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
        print(f"[CALENDAR] File not found at {CALENDAR_FILE}, using empty list")
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


async def import_google_calendar(
    calendar_id: str = "primary",
    access_token: str = "",
    max_results: int = 25,
) -> dict:
    """
    Import upcoming events from Google Calendar into local calendar fixture.
    Supports OAuth bearer token or API key for public calendars.
    """
    calendar_id = (calendar_id or "primary").strip()
    token = (access_token or "").strip()
    max_results = max(1, min(int(max_results or 25), 100))

    if not token and not GOOGLE_CALENDAR_API_KEY:
        return {
            "ok": False,
            "imported": 0,
            "error": "Google credentials missing. Provide access_token or set GOOGLE_CALENDAR_API_KEY.",
        }

    time_min = datetime.utcnow().isoformat() + "Z"
    encoded_id = quote(calendar_id, safe="")
    url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_id}/events"

    params = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "timeMin": time_min,
        "maxResults": str(max_results),
    }
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        params["key"] = GOOGLE_CALENDAR_API_KEY

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", [])
    except Exception as e:
        return {"ok": False, "imported": 0, "error": f"Google import failed: {e}"}

    events = _load_calendar()
    existing_ids = {evt.get("id") for evt in events}
    imported = 0

    for item in items:
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date") or start
        if not start:
            continue

        event_id = f"gcal_{item.get('id', uuid.uuid4().hex[:8])}"
        if event_id in existing_ids:
            continue

        events.append({
            "id": event_id,
            "title": item.get("summary", "Google Calendar Event"),
            "start": start,
            "end": end,
            "notes": item.get("description", ""),
            "location": item.get("location", ""),
            "source": "google",
        })
        existing_ids.add(event_id)
        imported += 1

    if imported:
        _save_calendar(events)

    return {"ok": True, "imported": imported, "events_seen": len(items)}
