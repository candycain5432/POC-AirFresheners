"""
Turn a YouTube or TikTok link into a safe embed URL for an <iframe>.

Only these two sites are allowed, and the video ID is checked against a
strict pattern, so an admin typo (or a malicious link) can never make the
page embed some other website.

    embed_info("https://youtu.be/abc123XYZ_-")
      -> {"src": "https://www.youtube-nocookie.com/embed/abc123XYZ_-",
          "provider": "youtube", "vertical": False, "url": <original link>}
"""
import re
from urllib.parse import parse_qs, urlparse

YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
TIKTOK_ID = re.compile(r"^\d{8,25}$")


def _youtube_id(parsed):
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
    path = parsed.path.strip("/").split("/")
    if host == "youtu.be" and path and path[0]:
        return path[0], False
    if host in ("youtube.com", "youtube-nocookie.com"):
        if path[0] == "watch":
            return parse_qs(parsed.query).get("v", [""])[0], False
        if path[0] in ("shorts", "embed", "live") and len(path) > 1:
            return path[1], path[0] == "shorts"   # Shorts are vertical videos
    return None, False


def _tiktok_id(parsed):
    host = parsed.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host != "tiktok.com":
        return None
    # Links look like https://www.tiktok.com/@user/video/7300000000000000001
    match = re.search(r"/video/(\d+)", parsed.path)
    return match.group(1) if match else None


def embed_info(url):
    """Return embed details for a supported video link, or None."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return None

    video_id, vertical = _youtube_id(parsed)
    if video_id and YOUTUBE_ID.match(video_id):
        return {"provider": "youtube", "vertical": vertical, "url": url,
                "src": f"https://www.youtube-nocookie.com/embed/{video_id}"}

    video_id = _tiktok_id(parsed)
    if video_id and TIKTOK_ID.match(video_id):
        return {"provider": "tiktok", "vertical": True, "url": url,
                "src": f"https://www.tiktok.com/embed/v2/{video_id}"}
    return None
