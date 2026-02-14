"""
Vuddy Backend — Campus Events Service.
Loads seeded events from JSON, filters by time range and tags.
Schema must match shared/events.schema.json.
"""

import json
import os
import re
import hashlib
import subprocess
from html import unescape
from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote, urlparse, urlencode
from zoneinfo import ZoneInfo
import httpx

EVENTS_DATA_PATH = os.getenv("EVENTS_DATA_PATH", os.path.join("data", "events_seed.json"))
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY", "")
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
DUCKDUCKGO_HTML_URL = "https://duckduckgo.com/html/"
GMU_ICS_URL = os.getenv("GMU_ICS_URL", "https://mason360.gmu.edu/ical/gmu/ical_gmu.ics")
US_EASTERN = ZoneInfo("America/New_York")
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

    # Prefer official school feed when available.
    school_feed = _search_school_ics_events(query=query, city=city, size=size)
    if school_feed.get("ok") and school_feed.get("events"):
        _set_realtime_cache(cache_key, school_feed)
        return school_feed

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

    web_result = _search_web_events(query=query, city=city, size=size)
    if web_result.get("ok") and web_result.get("events"):
        _set_realtime_cache(cache_key, web_result)
        return web_result

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
    now = datetime.now()
    # Time-anchored query keeps results from getting stale.
    query = f"campus student university events {now.strftime('%B %Y')}"
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
    source = "seed_fallback"

    # If query match is empty, return upcoming items so UI is never blank.
    if not top:
        source = "seed_fallback_default"
        now = datetime.now()
        upcoming = []
        for event in events:
            location = event.get("location", "")
            start_raw = event.get("start", "")
            try:
                start_dt = datetime.fromisoformat(start_raw)
            except Exception:
                continue
            if start_dt < now - timedelta(days=1):
                continue
            if city_q and city_q not in location.lower():
                continue
            upcoming.append(event)

        # If strict city matching produces no results, relax it.
        if not upcoming:
            for event in events:
                start_raw = event.get("start", "")
                try:
                    start_dt = datetime.fromisoformat(start_raw)
                except Exception:
                    continue
                if start_dt >= now - timedelta(days=1):
                    upcoming.append(event)
        upcoming.sort(key=lambda evt: evt.get("start", ""))
        top = upcoming[:size]
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
    return {"ok": True, "events": normalized, "source": source}


def _search_school_ics_events(query: str, city: str = "", size: int = 10) -> dict:
    """
    Pull events from school ICS feed (GMU Mason360) when location/context matches.
    """
    q = (query or "").lower()
    city_lower = (city or "").lower()
    is_gmu_context = any(token in f"{q} {city_lower}" for token in ["gmu", "mason", "fairfax"])
    if not is_gmu_context and "campus" not in q and "student" not in q:
        return {"ok": True, "events": [], "source": "school_ics", "live": False}

    try:
        ics_text = _fetch_text_url(
            GMU_ICS_URL,
            {"User-Agent": "Vuddy/1.0"},
            None,
            6.0,
        )
        events = _parse_school_ics(
            ics_text=ics_text,
            query=query,
            city=city,
            size=size,
        )
        return {
            "ok": True,
            "events": events,
            "source": "gmu_mason360_ics",
            "live": True,
        }
    except Exception as e:
        print(f"[EVENTS] School ICS fetch failed: {e}")
        return {"ok": False, "events": [], "source": "school_ics", "live": False, "error": str(e)}


def _search_web_events(query: str, city: str = "", size: int = 10) -> dict:
    """
    Live web search fallback using DuckDuckGo HTML results.
    No API key required; returns source links users can click through.
    """
    search_terms = " ".join(part for part in [query.strip(), city.strip(), "events"] if part).strip()
    if not search_terms:
        return {"ok": False, "events": [], "source": "web_search", "live": False}

    try:
        html = _fetch_text_url(
            DUCKDUCKGO_HTML_URL,
            {"User-Agent": "Vuddy/1.0"},
            {"q": search_terms},
            6.0,
        )
        events = _parse_duckduckgo_events(html, city=city, size=size)
        return {
            "ok": True,
            "events": events,
            "source": "web_search",
            "live": True,
        }
    except Exception as e:
        print(f"[EVENTS] Web search fallback failed: {e}")
        return {"ok": False, "events": [], "source": "web_search", "live": False, "error": str(e)}


def _parse_duckduckgo_events(html: str, city: str = "", size: int = 10) -> list[dict]:
    anchor_pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    anchors = anchor_pattern.findall(html)
    snippets = snippet_pattern.findall(html)
    events: list[dict] = []
    seen_urls: set[str] = set()

    for idx, (raw_href, raw_title) in enumerate(anchors):
        if len(events) >= size:
            break
        url = _clean_ddg_link(raw_href)
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = _strip_html(raw_title)
        snippet = _strip_html(snippets[idx]) if idx < len(snippets) else ""
        if not title:
            continue

        if city and city.lower() not in f"{title} {snippet}".lower():
            # Keep search results broad, but prefer city-matching first.
            if len(events) < max(2, size // 3):
                continue

        events.append({
            "id": f"web_{idx}",
            "title": title,
            "start": "",
            "end": "",
            "location": city,
            "description": snippet,
            "tags": ["Live", "Web"],
            "url": url,
        })

    return events


def _fetch_text_url(url: str, headers: dict[str, str] | None, params: dict[str, str] | None, timeout_sec: float) -> str:
    query = urlencode(params or {})
    final_url = f"{url}?{query}" if query else url
    cmd = [
        "curl",
        "-fsSL",
        "--max-time",
        str(int(timeout_sec)),
        "--connect-timeout",
        "3",
    ]
    for key, value in (headers or {}).items():
        cmd.extend(["-H", f"{key}: {value}"])
    cmd.append(final_url)
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        timeout=max(2, int(timeout_sec) + 1),
    )
    return completed.stdout


def _parse_school_ics(ics_text: str, query: str, city: str = "", size: int = 10) -> list[dict]:
    lines = _unfold_ics_lines(ics_text)
    events: list[dict] = []
    block: dict[str, str] = {}
    in_event = False
    now_et = datetime.now(US_EASTERN)
    cutoff = now_et + timedelta(days=90)
    query_tokens = [t for t in re.split(r"[\W_]+", (query or "").lower()) if len(t) > 2]

    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event = True
            block = {}
            continue
        if line == "END:VEVENT":
            if block:
                parsed = _normalize_ics_event(block, city=city)
                if parsed and parsed["_start_dt"] >= now_et - timedelta(days=1) and parsed["_start_dt"] <= cutoff:
                    haystack = f"{parsed['title']} {parsed['description']} {parsed['location']}".lower()
                    if not query_tokens or any(token in haystack for token in query_tokens):
                        parsed.pop("_start_dt", None)
                        events.append(parsed)
            in_event = False
            block = {}
            continue
        if not in_event:
            continue

        key, sep, value = line.partition(":")
        if not sep:
            continue
        field = key.split(";", 1)[0].upper()
        if field in {"SUMMARY", "DTSTART", "DTEND", "LOCATION", "DESCRIPTION", "URL"}:
            block[field] = value.strip()

    events.sort(key=lambda evt: evt.get("start", ""))
    return events[:size]


def _unfold_ics_lines(ics_text: str) -> list[str]:
    raw_lines = (ics_text or "").replace("\r\n", "\n").split("\n")
    lines: list[str] = []
    for raw in raw_lines:
        if not lines:
            lines.append(raw)
            continue
        if raw.startswith(" ") or raw.startswith("\t"):
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _normalize_ics_event(block: dict[str, str], city: str = "") -> dict | None:
    start_dt = _parse_ics_datetime(block.get("DTSTART", ""))
    if not start_dt:
        return None
    end_dt = _parse_ics_datetime(block.get("DTEND", ""))
    if not end_dt:
        end_dt = start_dt + timedelta(hours=1)

    title = block.get("SUMMARY", "").strip()
    if not title:
        return None
    location = block.get("LOCATION", "").strip() or city
    description = _decode_ics_text(block.get("DESCRIPTION", "").strip())
    url = block.get("URL", "").strip()

    return {
        "id": f"ics_{hashlib.sha1(f'{title}|{start_dt.isoformat()}|{location}'.encode()).hexdigest()[:10]}",
        "title": title,
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "location": location,
        "description": description,
        "tags": ["Campus", "Live"],
        "url": url,
        "_start_dt": start_dt,
    }


def _parse_ics_datetime(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None

    # Date-only format: YYYYMMDD
    if re.fullmatch(r"\d{8}", raw):
        dt = datetime.strptime(raw, "%Y%m%d")
        return dt.replace(tzinfo=US_EASTERN)

    # UTC datetime format: YYYYMMDDTHHMMSSZ
    if re.fullmatch(r"\d{8}T\d{6}Z", raw):
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(US_EASTERN)

    # Local datetime format: YYYYMMDDTHHMMSS
    if re.fullmatch(r"\d{8}T\d{6}", raw):
        return datetime.strptime(raw, "%Y%m%dT%H%M%S").replace(tzinfo=US_EASTERN)

    return None


def _decode_ics_text(text: str) -> str:
    return (
        text.replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _clean_ddg_link(url: str) -> str:
    href = unescape((url or "").strip())
    if not href:
        return ""
    if href.startswith("//"):
        href = f"https:{href}"
    if href.startswith("/l/?"):
        parsed = urlparse(href)
        raw = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(raw) if raw else ""
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return ""


def _strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw or "")
    return unescape(text).strip()


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
