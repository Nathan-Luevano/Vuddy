"""
Vuddy Backend — School Configuration.
Supports multiple Virginia schools. Frontend sends school selection,
backend adjusts system prompt and school-specific details.
"""

import os

# Default school from env, can be overridden per-session via API
ACTIVE_SCHOOL = os.getenv("SCHOOL", "gmu")


# School profiles: mascot, colors, locations, personality flavor
SCHOOLS = {
    "gmu": {
        "name": "George Mason University",
        "short": "Mason",
        "mascot": "The Patriot",
        "colors": ["green", "gold"],
        "city": "Fairfax, VA",
        "common_locations": [
            "Johnson Center (JC)",
            "Fenwick Library",
            "Innovation Hall",
            "EagleBank Arena",
            "The Hub",
            "Dewberry Hall",
            "RAC (Recreation Center)",
            "North Quad",
        ],
        "personality": "You're the campus buddy at George Mason University in Fairfax, VA. "
                       "Students call the main hub the JC (Johnson Center). "
                       "The mascot is The Patriot. School colors are green and gold. "
                       "Mason is known for its diverse, welcoming community.",
    },
    "jmu": {
        "name": "James Madison University",
        "short": "JMU",
        "mascot": "Duke Dog",
        "colors": ["purple", "gold"],
        "city": "Harrisonburg, VA",
        "common_locations": [
            "Festival Conference Center",
            "Carrier Library",
            "ISAT Building",
            "Atlantic Union Bank Center",
            "D-Hall (Dining)",
            "The Quad",
            "University Recreation Center (UREC)",
            "Wilson Hall",
        ],
        "personality": "You're the campus buddy at James Madison University in Harrisonburg, VA. "
                       "Students love D-Hall and The Quad. "
                       "The mascot is Duke Dog. School colors are purple and gold. "
                       "JMU is known for its strong school spirit and beautiful Shenandoah Valley setting.",
    },
    "uva": {
        "name": "University of Virginia",
        "short": "UVA",
        "mascot": "Cavalier (Wahoo)",
        "colors": ["orange", "navy blue"],
        "city": "Charlottesville, VA",
        "common_locations": [
            "The Rotunda",
            "Alderman Library",
            "Newcomb Hall",
            "John Paul Jones Arena",
            "The Corner",
            "Lawn Rooms",
            "Rice Hall",
            "Scott Stadium",
        ],
        "personality": "You're the campus buddy at the University of Virginia in Charlottesville, VA. "
                       "Students call themselves Wahoos (or Hoos). "
                       "The mascot is the Cavalier. School colors are orange and navy blue. "
                       "UVA is founded by Thomas Jefferson and students cherish the Lawn and The Corner.",
    },
    "vt": {
        "name": "Virginia Tech",
        "short": "VT",
        "mascot": "HokieBird",
        "colors": ["maroon", "burnt orange"],
        "city": "Blacksburg, VA",
        "common_locations": [
            "Torgersen Hall",
            "Newman Library",
            "Squires Student Center",
            "Cassell Coliseum",
            "Lane Stadium",
            "The Drillfield",
            "McBryde Hall",
            "War Memorial Hall",
        ],
        "personality": "You're the campus buddy at Virginia Tech in Blacksburg, VA. "
                       "Students are Hokies — Let's Go! "
                       "The mascot is the HokieBird. School colors are maroon and burnt orange. "
                       "VT is known for Ut Prosim (That I May Serve) and incredible game day energy.",
    },
}


def get_school(school_id: str | None = None) -> dict:
    """Get school config by ID. Falls back to active school, then GMU."""
    sid = (school_id or ACTIVE_SCHOOL).lower().strip()
    return SCHOOLS.get(sid, SCHOOLS["gmu"])


def set_active_school(school_id: str) -> dict:
    """Set the active school for this session."""
    global ACTIVE_SCHOOL
    sid = school_id.lower().strip()
    if sid not in SCHOOLS:
        return {"ok": False, "error": f"Unknown school: {school_id}", "valid": list(SCHOOLS.keys())}
    ACTIVE_SCHOOL = sid
    return {"ok": True, "school": SCHOOLS[sid]["name"], "short": SCHOOLS[sid]["short"]}


def list_schools() -> dict:
    """List all supported schools."""
    return {
        "ok": True,
        "schools": [
            {"id": sid, "name": s["name"], "short": s["short"], "mascot": s["mascot"]}
            for sid, s in SCHOOLS.items()
        ],
    }


def get_school_prompt_context() -> str:
    """Generate school-specific context for the LLM system prompt."""
    school = get_school()
    return school["personality"]
