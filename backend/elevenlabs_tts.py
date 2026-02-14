"""
Vuddy Backend — ElevenLabs TTS Voice Generation.
Caches audio by content hash. Graceful fallback on API failure.
"""

import hashlib
import os

import httpx

TTS_OUTPUT_DIR = os.path.join("data", "audio", "tts")

# Max text length — truncate if longer
MAX_TEXT_LENGTH = 500


def _tts_enabled() -> bool:
    raw = os.getenv("ENABLE_TTS", "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _get_api_key() -> str:
    """Read API key at call time (not import time) so dotenv has loaded."""
    return os.getenv("ELEVENLABS_API_KEY", "")


def _get_voice_id() -> str:
    return os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")


def _get_model() -> str:
    return os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5")


async def synthesize(text: str) -> str | None:
    """
    Synthesize text to speech via ElevenLabs API.
    Returns file path on success, None on failure (frontend uses browser speechSynthesis as backup).
    """
    if not _tts_enabled():
        print("[TTS] ENABLE_TTS is disabled, skipping synthesis")
        return None

    if not text or not text.strip():
        return None

    api_key = _get_api_key()
    voice_id = _get_voice_id()
    model_id = _get_model()

    # Truncate if too long
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]

    # Normalize only for cache key (preserve original text for actual synthesis).
    cache_text = " ".join(text.strip().split())

    # Cache key: SHA-256 of voice_id + text
    cache_key = hashlib.sha256(f"{voice_id}{cache_text}".encode()).hexdigest()[:16]
    filename = f"{cache_key}.mp3"
    filepath = os.path.join(TTS_OUTPUT_DIR, filename)

    # Cache hit: return path immediately
    if os.path.exists(filepath):
        print(f"[TTS] Cache hit -> {filepath}")
        return filepath

    # Ensure output directory exists
    os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

    if not api_key:
        print("[TTS] No ElevenLabs API key set, returning None (text-only fallback)")
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            }
            payload = {
                "text": text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            }
            resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code != 200:
                # Log the actual error from ElevenLabs for debugging
                try:
                    error_body = resp.json()
                except Exception:
                    error_body = resp.text[:300]
                print(f"[TTS] ElevenLabs {resp.status_code} error:")
                print(f"[TTS]   Response: {error_body}")
                if resp.status_code == 401:
                    print(f"[TTS]   Key length: {len(api_key)}, starts with: {api_key[:6]}...")
                    print(f"[TTS]   Check: is the key correct? No quotes in .env?")
                return None

            with open(filepath, "wb") as f:
                f.write(resp.content)

            print(f"[TTS] Synthesized -> {filepath}")
            return filepath

    except httpx.TimeoutException:
        print("[TTS] ElevenLabs API timed out (30s), returning None")
        return None
    except httpx.ConnectError as e:
        print(f"[TTS] Cannot reach ElevenLabs API ({e}), returning None")
        return None
    except Exception as e:
        print(f"[TTS] Unexpected error: {type(e).__name__}: {e}")
        return None
