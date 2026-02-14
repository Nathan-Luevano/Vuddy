"""
Vuddy Backend — Study Session Timer.
In-memory session store. Pomodoro-style study sessions.
"""

import uuid
from datetime import datetime, timedelta

# In-memory session store
_sessions: dict[str, dict] = {}


def start_session(topic: str, duration_min: int = 25) -> dict:
    """
    Start a new study session.
    Returns: {ok: bool, session_id: str, end_time: str}
    """
    try:
        session_id = f"study_{uuid.uuid4().hex[:6]}"
        now = datetime.now()
        end_time = now + timedelta(minutes=duration_min)

        _sessions[session_id] = {
            "session_id": session_id,
            "topic": topic,
            "duration_min": duration_min,
            "start_time": now.isoformat(),
            "end_time": end_time.isoformat(),
            "active": True,
        }

        return {
            "ok": True,
            "session_id": session_id,
            "end_time": end_time.isoformat(),
        }

    except Exception as e:
        print(f"[STUDY] Error starting session: {e}")
        return {"ok": False, "error": str(e)}


def stop_session(session_id: str) -> dict:
    """
    Stop an active study session.
    Returns: {ok: bool, elapsed_min: float}
    """
    try:
        session = _sessions.get(session_id)
        if not session:
            return {"ok": False, "error": f"Session {session_id} not found"}

        if not session["active"]:
            return {"ok": False, "error": f"Session {session_id} already stopped"}

        session["active"] = False
        start_time = datetime.fromisoformat(session["start_time"])
        elapsed = (datetime.now() - start_time).total_seconds() / 60.0

        session["elapsed_min"] = round(elapsed, 1)
        session["stopped_at"] = datetime.now().isoformat()

        return {
            "ok": True,
            "elapsed_min": round(elapsed, 1),
        }

    except Exception as e:
        print(f"[STUDY] Error stopping session: {e}")
        return {"ok": False, "error": str(e)}


def get_active_sessions() -> list[dict]:
    """Get all currently active study sessions."""
    return [s for s in _sessions.values() if s.get("active")]
