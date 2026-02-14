#!/usr/bin/env python3
"""Smoke test: connect to backend WS and send a test message.

Usage:
    python scripts/smoke_ws_client.py
    python scripts/smoke_ws_client.py --url ws://localhost:8000/ws
    python scripts/smoke_ws_client.py --timeout 30

Requires: pip install websockets
"""
import argparse
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("[FAIL] websockets not installed. Run: pip install websockets")
    sys.exit(1)


PASS = 0
FAIL = 0
WARN = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def warn(msg):
    global WARN
    WARN += 1
    print(f"  [WARN] {msg}")


async def test_connect(ws_url, timeout):
    print(f"\n1. Connecting to {ws_url}...")
    try:
        ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=5.0)
    except Exception as e:
        fail(f"Could not connect: {e}")
        return None
    ok("WebSocket connected")

    # Expect assistant_state on connect
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        msg = json.loads(raw)
    except Exception as e:
        fail(f"No initial message: {e}")
        return ws

    if msg.get("type") != "assistant_state":
        fail(f"Expected type=assistant_state, got type={msg.get('type')}")
    else:
        ok(f"Initial state: {msg.get('state')}")

    if msg.get("state") != "idle":
        warn(f"Expected state=idle, got state={msg.get('state')}")

    provider = msg.get("llm_provider", "unknown")
    print(f"  LLM Provider: {provider}")

    hw_mode = msg.get("hardware_mode", "not reported")
    print(f"  Hardware Mode: {hw_mode}")

    return ws


async def test_chat(ws, timeout):
    print("\n2. Sending chat message...")
    await ws.send(json.dumps({"type": "chat", "text": "what events are happening tonight?"}))
    ok("Sent chat message")

    print("\n3. Collecting responses...")
    received_types = []
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            msg_type = msg.get("type", "unknown")
            received_types.append(msg_type)
            preview = json.dumps(msg)[:150]
            print(f"  [RECV] {msg_type}: {preview}")

            if msg_type == "assistant_audio_ready":
                break
            if msg_type == "error":
                warn(f"Error from backend: {msg.get('message')}")
                break
            if msg_type == "assistant_text" and "assistant_audio_ready" not in received_types:
                # Text came but audio might not come (ElevenLabs not configured)
                try:
                    raw2 = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg2 = json.loads(raw2)
                    received_types.append(msg2.get("type"))
                    print(f"  [RECV] {msg2.get('type')}: {json.dumps(msg2)[:150]}")
                except asyncio.TimeoutError:
                    pass
                break
    except asyncio.TimeoutError:
        warn("Timed out waiting for responses")

    print("\n4. Verifying message flow...")
    if "assistant_state" in received_types:
        ok("Got assistant_state update")
    else:
        warn("No assistant_state update (might be OK)")

    if "assistant_text" in received_types:
        ok("Got assistant_text response")
    else:
        fail("Missing assistant_text response")

    if "assistant_audio_ready" in received_types:
        ok("Got assistant_audio_ready")
    else:
        warn("No audio response (ElevenLabs may not be configured)")


async def test_health(base_url):
    import urllib.request
    print("\n5. Checking REST health endpoint...")
    try:
        url = base_url.replace("ws://", "http://").replace("/ws", "/health")
        req = urllib.request.urlopen(url, timeout=5)
        data = json.loads(req.read())
        if data.get("ok"):
            ok(f"Health OK: provider={data.get('llm_provider')}, hardware={data.get('hardware_mode')}")
        else:
            fail(f"Health not OK: {data}")
    except Exception as e:
        warn(f"Health check failed: {e}")


async def main(ws_url, timeout):
    print("=" * 50)
    print("  Vuddy Smoke Test")
    print("=" * 50)

    ws = await test_connect(ws_url, timeout)
    if ws is None:
        print(f"\nResults: {PASS} passed, {FAIL} failed, {WARN} warnings")
        sys.exit(1)

    await test_chat(ws, timeout)
    await ws.close()

    await test_health(ws_url)

    print("\n" + "=" * 50)
    print(f"  Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print("=" * 50)

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vuddy WebSocket smoke test")
    parser.add_argument("--url", default="ws://localhost:8000/ws", help="WebSocket URL")
    parser.add_argument("--timeout", type=int, default=20, help="Response timeout in seconds")
    args = parser.parse_args()
    asyncio.run(main(args.url, args.timeout))
