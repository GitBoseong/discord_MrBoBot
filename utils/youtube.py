from typing import List

from yt_dlp import YoutubeDL


BASE_YDL_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "source_address": "0.0.0.0",
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
}


def _extract(query: str, *, search_limit: int = 1) -> dict:
    opts = {
        **BASE_YDL_OPTS,
        "default_search": f"ytsearch{search_limit}",
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(query, download=False)


def _first_entry(info: dict) -> dict:
    entries = info.get("entries")
    if entries:
        for entry in entries:
            if entry:
                return entry
        raise ValueError("검색 결과가 비어 있습니다.")
    return info


def get_youtube_info(query: str) -> dict:
    """Return a playable yt-dlp info dict for a YouTube URL or search term."""
    return _first_entry(_extract(query, search_limit=1))


def search_youtube(query: str, limit: int = 5) -> List[dict]:
    """Return up to ``limit`` playable yt-dlp info dicts for a search term."""
    info = _extract(query, search_limit=limit)
    entries = info.get("entries") or [info]
    return [entry for entry in entries if entry][:limit]


def search_youtube_info(query: str) -> dict:
    """Backward-compatible alias for older code."""
    return get_youtube_info(query)
