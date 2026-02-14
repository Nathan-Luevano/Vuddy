"""
Vuddy Backend — Personalized Recommendations.
Scores events by interest match (keyword overlap) against user profile.
"""

from backend import events_service, profile_store


def get_recommendations(count: int = 3) -> dict:
    """
    Get personalized event recommendations based on user interests.
    Returns: {ok: bool, events: [...], reasons: [...]}
    """
    try:
        # Load user profile
        profile = profile_store.load_profile()
        user_interests = set(
            i.lower() for i in profile.get("interests", [])
        )

        # Get all upcoming events (next 72 hours to have a good pool)
        all_events_result = events_service.get_events("today")
        all_events = all_events_result.get("events", [])

        # Also include tomorrow and weekend events for a bigger pool
        for time_range in ["tomorrow", "this weekend"]:
            more = events_service.get_events(time_range)
            for evt in more.get("events", []):
                # Deduplicate by title+start
                key = (evt.get("title"), evt.get("start"))
                if not any(
                    (e.get("title"), e.get("start")) == key for e in all_events
                ):
                    all_events.append(evt)

        if not all_events:
            return {"ok": True, "events": [], "reasons": []}

        # Score each event by keyword overlap with user interests
        scored = []
        for event in all_events:
            event_keywords = set()
            # Add tags
            for tag in event.get("tags", []):
                event_keywords.add(tag.lower())
            # Add words from title and description
            for field in ["title", "description"]:
                for word in event.get(field, "").lower().split():
                    if len(word) > 3:  # Skip short words
                        event_keywords.add(word)

            overlap = user_interests & event_keywords
            score = len(overlap)

            # If no interests set, give everyone a base score for variety
            if not user_interests:
                score = 1

            reason = _generate_reason(event, overlap, user_interests)
            scored.append((score, event, reason))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:count]

        events = [item[1] for item in top]
        reasons = [item[2] for item in top]

        return {"ok": True, "events": events, "reasons": reasons}

    except Exception as e:
        print(f"[RECOMMENDER] Error: {e}")
        return {"ok": False, "events": [], "reasons": [], "error": str(e)}


def _generate_reason(event: dict, overlap: set, user_interests: set) -> str:
    """Generate a human-readable reason for the recommendation."""
    title = event.get("title", "this event")

    if overlap:
        matched = ", ".join(sorted(overlap)[:3])
        return f"Matches your interest in {matched}"

    if not user_interests:
        tags = event.get("tags", [])
        if tags:
            return f"Popular {tags[0]} event on campus"
        return "Happening soon on campus"

    return f"You might enjoy {title}"
