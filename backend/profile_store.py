"""
Vuddy Backend — User Profile Store.
JSON file at data/profile/user_profile.json.
Privacy: only update when user explicitly confirms.
"""

import json
import os

PROFILE_FILE = os.path.join("data", "profile", "user_profile.json")

DEFAULT_PROFILE = {
    "interests": [],
    "preferred_times": [],
    "study_habits": {},
    "preferences": {},
}


def load_profile() -> dict:
    """Load user profile from JSON file. Returns default if file doesn't exist."""
    try:
        with open(PROFILE_FILE, "r") as f:
            profile = json.load(f)
            # Ensure all default keys exist
            for key, default_val in DEFAULT_PROFILE.items():
                if key not in profile:
                    profile[key] = default_val
            return profile
    except FileNotFoundError:
        # Create default profile
        save_profile(DEFAULT_PROFILE)
        return dict(DEFAULT_PROFILE)
    except json.JSONDecodeError:
        print(f"[PROFILE] Invalid JSON in {PROFILE_FILE}, resetting to default")
        save_profile(DEFAULT_PROFILE)
        return dict(DEFAULT_PROFILE)


def save_profile(profile: dict) -> None:
    """Save user profile to JSON file."""
    os.makedirs(os.path.dirname(PROFILE_FILE), exist_ok=True)
    with open(PROFILE_FILE, "w") as f:
        json.dump(profile, f, indent=2)


def update_profile(updates: dict) -> dict:
    """
    Merge updates into existing profile and save.
    Returns the updated profile.
    """
    profile = load_profile()
    profile.update(updates)
    save_profile(profile)
    return profile


def get_profile_context() -> str:
    """
    Generate a context string for the LLM system prompt.
    Returns a human-readable summary of the user's profile.
    """
    profile = load_profile()
    parts = []

    interests = profile.get("interests", [])
    if interests:
        parts.append(f"User interests: {', '.join(interests)}")

    preferred_times = profile.get("preferred_times", [])
    if preferred_times:
        parts.append(f"Preferred times: {', '.join(preferred_times)}")

    study_habits = profile.get("study_habits", {})
    if study_habits:
        habits = ", ".join(f"{k}: {v}" for k, v in study_habits.items())
        parts.append(f"Study habits: {habits}")

    preferences = profile.get("preferences", {})
    if preferences:
        prefs = ", ".join(f"{k}: {v}" for k, v in preferences.items())
        parts.append(f"Preferences: {prefs}")

    if not parts:
        return "No user profile information available yet."

    return ". ".join(parts) + "."
