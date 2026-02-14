import asyncio
import os
import sys
import json
import httpx
import websockets
# from termcolor import colored

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"

REQUIRED_FILES = [
    "backend/__init__.py",
    "backend/main.py",
    "backend/brain.py",
    "backend/constants.py",
    "backend/llm_provider.py",
    "backend/elevenlabs_tts.py",
    "backend/events_service.py",
    "backend/calendar_service.py",
    "backend/study_service.py",
    "backend/profile_store.py",
    "backend/recommender.py",
    "backend/spotify_links.py",
    "backend/hardware_interface.py",
    "backend/school_config.py",
    "backend/tools.py",
    "data/fixtures/calendar.json",
    "data/profile/user_profile.json",
    ".env"
]

def log(msg, color="white"):
    print(msg)

def check_files():
    log("--- 1. File Structure Check ---", "cyan")
    missing = []
    for f in REQUIRED_FILES:
        if os.path.exists(f):
            log(f"✅ Found {f}", "green")
        else:
            log(f"❌ MISSING {f}", "red")
            missing.append(f)
    return len(missing) == 0

async def check_api():
    log("\n--- 2. REST API Check ---", "cyan")
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        # Health
        try:
            r = await client.get("/health")
            if r.status_code == 200:
                data = r.json()
                log(f"✅ /health: OK (LLM={data.get('llm_provider')}, TTS={data.get('elevenlabs')})", "green")
            else:
                log(f"❌ /health: Failed ({r.status_code})", "red")
                return False
        except Exception as e:
            log(f"❌ Server unreachable: {e}", "red")
            return False

        # Events
        r = await client.get("/api/events")
        if r.status_code == 200 and isinstance(r.json(), list):
            log(f"✅ /api/events: OK ({len(r.json())} items)", "green")
        else:
            log(f"❌ /api/events: Failed", "red")

        # Calendar
        r = await client.get("/api/calendar/summary")
        if r.status_code == 200:
            log(f"✅ /api/calendar/summary: OK", "green")
        else:
            log(f"❌ /api/calendar/summary: Failed", "red")

        # Profile
        r = await client.get("/api/profile")
        if r.status_code == 200:
            log(f"✅ /api/profile: OK", "green")
        else:
            log(f"❌ /api/profile: Failed", "red")
            
        # APIs School
        r = await client.get("/api/school")
        if r.status_code == 200:
            log(f"✅ /api/school: OK ({r.json().get('short')})", "green")
        else:
            log(f"❌ /api/school: Failed", "red")

    return True

async def check_ws():
    log("\n--- 3. WebSocket Chat Check ---", "cyan")
    try:
        async with websockets.connect(WS_URL, open_timeout=5) as ws:
            # Initial state
            init_msg = json.loads(await ws.recv())
            log(f"✅ WS Connected (State: {init_msg.get('state')})", "green")

            # Send Chat
            log("Sending: 'Hello Vuddy'", "yellow")
            await ws.send(json.dumps({"type": "chat", "text": "Hello Vuddy"}))

            # Wait for response
            got_audio = False
            got_text = False
            
            while not (got_audio and got_text):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    mtype = msg.get("type")
                    
                    if mtype == "assistant_text":
                        log(f"✅ Received Text: {msg.get('text')[:50]}...", "green")
                        got_text = True
                    elif mtype == "assistant_audio_ready":
                        log(f"✅ Received Audio URL: {msg.get('audio_url')}", "green")
                        got_audio = True
                    elif mtype == "error":
                        log(f"❌ WS Error: {msg.get('message')}", "red")
                        return False
                        
                except asyncio.TimeoutError:
                    log("❌ WS Timeout waiting for response", "red")
                    return False
                    
            log("✅ WebSocket Test Passed", "green")
            return True

    except Exception as e:
        log(f"❌ WebSocket Failed: {e}", "red")
        return False

async def main():
    if not check_files():
        log("\n❌ File check failed", "red")
        return
    
    if not await check_api():
        log("\n❌ API check failed", "red")
        return

    if not await check_ws():
        log("\n❌ WebSocket check failed", "red")
        return

    log("\n✨ ALL CHECKS PASSED ✨", "green")

if __name__ == "__main__":
    asyncio.run(main())
