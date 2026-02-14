"""
Vuddy Backend — FastAPI Application.
Main entry point. Startup, health, REST routes, WebSocket, CORS, audio serving.
"""

import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# Load .env file
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

from backend import brain, events_service, calendar_service, profile_store, school_config, elevenlabs_tts
from backend.constants import ASSISTANT_STATES, WS_TYPES_IN
from backend.hardware_interface import create_hardware
from backend.llm_provider import create_llm_provider

# Create the FastAPI app
app = FastAPI(title="Vuddy Backend", version="1.0.0")

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Range"],
)

# ── Startup Singletons ──────────────────────────────────────────────

llm_provider = None
hardware = None


@app.on_event("startup")
async def startup():
    """
    Startup sequence:
    1. Create LLM provider
    2. Create hardware (defaults to SimHardware)
    3. Init profile_store
    4. Load events data
    5. Verify ElevenLabs API key
    """
    global llm_provider, hardware

    # Step 1: LLM provider
    llm_provider = create_llm_provider()
    print(f"[STARTUP] LLM provider: {llm_provider.name}")

    # Step 2: Hardware
    hardware = create_hardware()
    print(f"[STARTUP] Hardware mode: {os.getenv('HARDWARE_MODE', 'sim')}")

    # Step 3: Init profile
    profile_store.load_profile()
    print("[STARTUP] Profile store initialized")

    # Step 4: Load events
    events_service._load_events()
    print("[STARTUP] Events data loaded")

    # Step 5: ElevenLabs check
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    if elevenlabs_key and elevenlabs_key != "your_elevenlabs_api_key_here":
        print("[STARTUP] ElevenLabs API key: set")
    else:
        print("[STARTUP] ElevenLabs API key: NOT SET (text-only fallback)")

    # Ensure audio output directory exists
    os.makedirs(os.path.join("data", "audio", "tts"), exist_ok=True)

    print("[STARTUP] Vuddy backend ready!")


# ── Health Endpoint ──────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check — returns status of all subsystems."""
    llm_ok = False
    if llm_provider:
        llm_ok = await llm_provider.health_check()

    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_ok = bool(elevenlabs_key and elevenlabs_key != "your_elevenlabs_api_key_here")

    school = school_config.get_school()
    return {
        "ok": True,
        "llm_provider": llm_provider.name if llm_provider else "none",
        "llm_reachable": llm_ok,
        "elevenlabs": elevenlabs_ok,
        "hardware_mode": os.getenv("HARDWARE_MODE", "sim"),
        "school": school["short"],
    }


# ── REST API Routes ──────────────────────────────────────────────────

@app.get("/api/events")
async def api_events(time_range: str = "today", tags: str = ""):
    """Get campus events filtered by time range and tags."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    result = events_service.get_events(time_range=time_range, tags=tag_list)
    return result


@app.get("/api/events/recommendations")
async def api_recommendations(count: int = 3):
    """Get personalized event recommendations."""
    from backend import recommender
    result = await recommender.get_recommendations(count=count)
    return result


@app.get("/api/events/search")
async def api_events_search(q: str, city: str = "", size: int = 10, days_ahead: int = 28):
    """Search real-time events (Ticketmaster) with seed fallback."""
    return await events_service.search_realtime_events(
        query=q,
        city=city,
        size=size,
        days_ahead=days_ahead,
    )


@app.get("/api/events/discover")
async def api_events_discover(city: str = "", size: int = 12, days_ahead: int = 28):
    """Get a live discovery feed for campus/student events."""
    return await events_service.discover_events(city=city, size=size, days_ahead=days_ahead)


@app.get("/api/calendar/summary")
async def api_calendar_summary(hours_ahead: int = 24):
    """Get upcoming calendar events."""
    result = calendar_service.get_summary(hours_ahead=hours_ahead)
    return result


@app.post("/api/calendar/add")
async def api_calendar_add(body: dict):
    """Add a reminder or event to the calendar."""
    result = calendar_service.add_item(
        title=body.get("title", ""),
        time_iso=body.get("time_iso", ""),
        notes=body.get("notes", ""),
    )
    return result


@app.post("/api/calendar/import/google")
async def api_calendar_import_google(body: dict):
    """Import Google Calendar events into local calendar store."""
    return await calendar_service.import_google_calendar(
        calendar_id=body.get("calendar_id", "primary"),
        access_token=body.get("access_token", ""),
        max_results=body.get("max_results", 25),
    )


@app.get("/api/calendar/google/auth-url")
async def api_calendar_google_auth_url(redirect_uri: str = ""):
    """Create Google OAuth consent URL for calendar access."""
    return calendar_service.get_google_oauth_url(redirect_uri=redirect_uri)


@app.post("/api/calendar/google/exchange")
async def api_calendar_google_exchange(body: dict):
    """
    Exchange Google OAuth code and import calendar events.
    Body: {code, state, redirect_uri?, calendar_id?, max_results?}
    """
    exchange = await calendar_service.exchange_google_oauth_code(
        code=body.get("code", ""),
        state=body.get("state", ""),
        redirect_uri=body.get("redirect_uri", ""),
    )
    if not exchange.get("ok"):
        return exchange

    imported = await calendar_service.import_google_calendar(
        calendar_id=body.get("calendar_id", "primary"),
        access_token=exchange.get("access_token", ""),
        max_results=body.get("max_results", 25),
    )
    if not imported.get("ok"):
        return imported
    return {"ok": True, **imported}


@app.get("/api/profile")
async def api_profile_get():
    """Get user profile."""
    profile = profile_store.load_profile()
    return {"ok": True, **profile}


@app.put("/api/profile")
async def api_profile_update(body: dict):
    """Update user profile."""
    profile_store.update_profile(body)
    return {"ok": True}


# ── School Selection ─────────────────────────────────────────────────

@app.get("/api/schools")
async def api_list_schools():
    """List all supported schools."""
    return school_config.list_schools()


@app.get("/api/school")
async def api_get_school():
    """Get the currently active school."""
    school = school_config.get_school()
    return {"ok": True, **school}


@app.put("/api/school")
async def api_set_school(body: dict):
    """Set the active school. Body: {"school": "gmu"}"""
    school_id = body.get("school", "")
    result = school_config.set_active_school(school_id)
    if result.get("ok"):
        brain.clear_history()  # Reset conversation for new school context
    return result


@app.get("/api/audio/tts/{filename}")
async def serve_tts_audio(filename: str, request: Request):
    """
    Serve TTS audio files with byte-range support.
    iOS Safari frequently requires 206 partial content for media playback.
    """
    filepath = os.path.join("data", "audio", "tts", filename)
    if not os.path.exists(filepath):
        return JSONResponse({"ok": False, "error": "File not found"}, status_code=404)

    file_size = os.path.getsize(filepath)
    range_header = request.headers.get("range")

    if range_header:
        try:
            range_spec = range_header.replace("bytes=", "")
            start_s, end_s = range_spec.split("-", 1)
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
            end = min(end, file_size - 1)
            length = max(0, end - start + 1)
        except Exception:
            start, end = 0, file_size - 1
            length = file_size

        def iter_chunk():
            with open(filepath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": "audio/mpeg",
        }
        return StreamingResponse(iter_chunk(), status_code=206, headers=headers, media_type="audio/mpeg")

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
    }
    return FileResponse(filepath, media_type="audio/mpeg", headers=headers)


@app.get("/api/audio/debug/last")
async def audio_debug_last():
    """Return recent generated TTS files for debugging playback/cache."""
    tts_dir = os.path.join("data", "audio", "tts")
    if not os.path.isdir(tts_dir):
        return {"ok": True, "files": []}

    files = []
    for name in os.listdir(tts_dir):
        if not name.endswith(".mp3"):
            continue
        path = os.path.join(tts_dir, name)
        try:
            stat = os.stat(path)
            files.append({
                "filename": name,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "url": f"/api/audio/tts/{name}",
            })
        except Exception:
            continue
    files.sort(key=lambda item: item["mtime"], reverse=True)
    return {"ok": True, "files": files[:10]}


@app.get("/api/audio/debug/ping")
async def audio_debug_ping(text: str = "This is a Vuddy ElevenLabs audio diagnostics ping.", force_new: bool = True):
    """
    Force-generate a short TTS sample and return stream URL.
    Useful for isolating generation vs browser playback failures.
    """
    audio_path = await elevenlabs_tts.synthesize(text=text, force_new=force_new)
    if not audio_path:
        return {"ok": False, "error": "TTS synthesis failed"}

    filename = os.path.basename(audio_path)
    try:
        size = os.path.getsize(audio_path)
    except Exception:
        size = 0
    return {
        "ok": True,
        "filename": filename,
        "size": size,
        "audio_url": f"/api/audio/tts/{filename}",
    }


# ── WebSocket ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket endpoint for real-time communication with frontend.
    """
    await ws.accept()

    # On connect: send initial state
    school = school_config.get_school()
    await ws.send_json({
        "type": "assistant_state",
        "state": "idle",
        "wake_word": os.getenv("WAKE_WORD", "hey vuddy"),
        "llm_provider": llm_provider.name if llm_provider else "ollama",
        "school": school["short"],
    })

    # Clear chat history for new connection
    brain.clear_history()

    current_turn_task: asyncio.Task | None = None

    async def set_idle_state():
        try:
            await ws.send_json({"type": "assistant_state", "state": "idle"})
        except Exception:
            pass
        if hardware:
            await hardware.set_led_state("idle")

    async def cancel_current_turn():
        nonlocal current_turn_task
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
            try:
                await current_turn_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"[WS] Turn task ended with error during cancel: {e}")
        current_turn_task = None

    async def run_turn(text: str):
        try:
            await brain.process_message(text, ws, llm_provider, hardware)
        except asyncio.CancelledError:
            # Interruption is expected; keep it silent.
            raise
        except Exception as e:
            print(f"[WS] Turn task error: {e}")
        finally:
            await set_idle_state()

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")

            if msg_type in ("transcript_final", "chat"):
                text = data.get("text", "").strip()
                if text:
                    await cancel_current_turn()
                    current_turn_task = asyncio.create_task(run_turn(text))

            elif msg_type == "start_listening":
                if hardware:
                    await hardware.set_led_state("listening")
                await ws.send_json({"type": "assistant_state", "state": "listening"})

            elif msg_type == "stop_listening":
                if hardware:
                    await hardware.set_led_state("idle")
                await ws.send_json({"type": "assistant_state", "state": "idle"})

            elif msg_type == "interrupt":
                await cancel_current_turn()
                await set_idle_state()

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
        await cancel_current_turn()
    except Exception as e:
        print(f"[WS] Error: {e}")
        await cancel_current_turn()
        try:
            await ws.send_json({
                "type": "error",
                "message": str(e),
                "recoverable": True,
            })
        except Exception:
            pass
