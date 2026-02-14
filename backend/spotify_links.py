"""
Vuddy Backend — Spotify Link Generator.
No OAuth required. Generates Spotify search URLs.
"""

from urllib.parse import quote


def search_link(query: str) -> dict:
    """
    Generate a Spotify search URL for the given query.
    Returns: {ok: bool, url: str, display_text: str}
    """
    try:
        if not query or not query.strip():
            return {"ok": False, "error": "Empty query"}

        encoded_query = quote(query.strip())
        url = f"https://open.spotify.com/search/{encoded_query}"
        display_text = f"Open in Spotify: {query.strip()}"

        return {
            "ok": True,
            "url": url,
            "display_text": display_text,
        }

    except Exception as e:
        print(f"[SPOTIFY] Error: {e}")
        return {"ok": False, "error": str(e)}
