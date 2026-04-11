"""Spotify playlist support.

Resolves a Spotify playlist URL to YouTube video IDs:
1. Fetch playlist track metadata via Spotify Web API (spotipy)
2. For each track, search YouTube Music via yt-dlp and pick the best match
   using duration filtering + title heuristics (avoids karaoke/covers/live)
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.config import settings
from app.services.youtube import PlaylistInfo, TrackInfo

logger = logging.getLogger(__name__)


# Penalty keywords commonly found in bad YouTube matches
BAD_KEYWORDS = [
    "karaoke",
    "instrumental",
    "cover",
    "live",
    "sped up",
    "slowed",
    "8d audio",
    "reverb",
    "nightcore",
    "remix",
    "lyrics video",
    "lyric video",
]

# Max seconds duration can differ from Spotify's value before we discard a candidate
DURATION_TOLERANCE = 10


@dataclass
class SpotifyTrack:
    title: str
    artist: str
    duration: int  # seconds


def is_spotify_url(url: str) -> bool:
    """Detect Spotify playlist URLs (https or spotify: scheme)."""
    if not url:
        return False
    if url.startswith("spotify:"):
        return True
    try:
        host = urlparse(url).netloc.lower()
        return host.endswith("spotify.com")
    except Exception:
        return False


def extract_spotify_playlist_id(url: str) -> str | None:
    """Extract playlist ID from a Spotify URL.

    Supports:
    - https://open.spotify.com/playlist/{id}
    - https://open.spotify.com/playlist/{id}?si=xxxx
    - spotify:playlist:{id}
    """
    if not url:
        return None
    match = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url)
    if match:
        return match.group(1)
    return None


def _fetch_spotify_tracks_sync(playlist_id: str) -> list[SpotifyTrack]:
    """Synchronous Spotify API call (wrapped in asyncio.to_thread by caller)."""
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials

    if not settings.spotify_client_id or not settings.spotify_client_secret:
        raise RuntimeError("Spotify credentials not configured")

    auth = SpotifyClientCredentials(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
    )
    sp = spotipy.Spotify(client_credentials_manager=auth)

    tracks: list[SpotifyTrack] = []
    results = sp.playlist_items(
        playlist_id,
        fields="items(track(name,duration_ms,artists(name))),next",
        limit=100,
    )

    while results:
        for item in results.get("items", []):
            track = item.get("track")
            if not track:
                continue
            name = track.get("name")
            artists = track.get("artists") or []
            if not name or not artists:
                continue
            tracks.append(
                SpotifyTrack(
                    title=name,
                    artist=artists[0].get("name", ""),
                    duration=(track.get("duration_ms") or 0) // 1000,
                )
            )
        if results.get("next"):
            results = sp.next(results)
        else:
            break

    return tracks


async def get_spotify_playlist_tracks(playlist_id: str) -> list[SpotifyTrack]:
    """Fetch track metadata for a Spotify playlist."""
    return await asyncio.to_thread(_fetch_spotify_tracks_sync, playlist_id)


def _score_candidate(
    entry: dict, target_title: str, target_artist: str, target_duration: int
) -> float:
    """Score a YouTube search result against a Spotify track.

    Higher score = better match. Returns -inf to reject.
    """
    entry_title = (entry.get("title") or "").lower()
    entry_duration = entry.get("duration") or 0

    # Reject if duration is way off (catches live versions, edits, wrong tracks)
    if target_duration > 0 and entry_duration > 0:
        diff = abs(entry_duration - target_duration)
        if diff > DURATION_TOLERANCE:
            return float("-inf")
        duration_score = max(0, DURATION_TOLERANCE - diff)
    else:
        duration_score = 0

    score = duration_score

    # Penalize bad versions unless the Spotify track itself contains the keyword
    # (e.g. don't penalize "Live at Wembley" if the original track is a live recording)
    target_lower = target_title.lower()
    for kw in BAD_KEYWORDS:
        if kw in entry_title and kw not in target_lower:
            score -= 5

    # Bonus for title match
    if target_lower in entry_title:
        score += 3

    # Bonus for artist match
    if target_artist and target_artist.lower() in entry_title:
        score += 2

    # Bonus for "official" tags which usually indicate canonical uploads
    if "official" in entry_title:
        score += 1

    return score


async def _search_youtube(query: str) -> list[dict]:
    """Run a yt-dlp search and return candidate entries as dicts."""
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        query,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        logger.warning(
            "yt-dlp search failed for %r (code=%s): %s",
            query,
            process.returncode,
            stderr.decode(errors="replace")[:500],
        )
        return []

    candidates: list[dict] = []
    for line in stdout.decode().strip().split("\n"):
        if not line.strip():
            continue
        try:
            candidates.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return candidates


async def find_youtube_match(track: SpotifyTrack) -> dict | None:
    """Find the best YouTube video ID for a Spotify track.

    Searches YouTube Music first (better music metadata), falls back to
    regular YouTube search if no acceptable match is found.
    """
    # Build query: "artist title"
    query = f"{track.artist} {track.title}".strip()
    if not query:
        return None

    # Try YouTube Music first
    for search_prefix in (f"ytmsearch5:{query}", f"ytsearch5:{query}"):
        candidates = await _search_youtube(search_prefix)
        if not candidates:
            continue

        best = None
        best_score = float("-inf")
        for entry in candidates:
            if not entry.get("id"):
                continue
            score = _score_candidate(entry, track.title, track.artist, track.duration)
            if score > best_score:
                best_score = score
                best = entry

        if best and best_score > float("-inf"):
            return best

    return None


async def extract_spotify_playlist_info(url: str) -> PlaylistInfo | None:
    """Fetch a Spotify playlist and resolve each track to a YouTube video.

    Raises exceptions with clear messages on failure. Missing tracks
    (no YouTube match found) are silently skipped.
    """
    playlist_id = extract_spotify_playlist_id(url)
    if not playlist_id:
        raise ValueError(f"Could not extract Spotify playlist ID from URL")

    logger.info("Fetching Spotify playlist %s", playlist_id)
    try:
        spotify_tracks = await get_spotify_playlist_tracks(playlist_id)
    except Exception as e:
        logger.exception("Spotify API call failed for playlist %s", playlist_id)
        raise RuntimeError(f"Spotify API error: {type(e).__name__}: {e}") from e

    if not spotify_tracks:
        raise RuntimeError(
            f"Spotify playlist {playlist_id} is empty or inaccessible"
        )

    logger.info(
        "Spotify playlist %s has %d tracks, resolving to YouTube...",
        playlist_id,
        len(spotify_tracks),
    )

    # Enforce MAX_TRACKS limit before expensive YouTube searches
    spotify_tracks = spotify_tracks[: settings.max_tracks]

    # Resolve each Spotify track to a YouTube video
    resolved: list[TrackInfo] = []
    unmatched: list[str] = []
    for idx, sp_track in enumerate(spotify_tracks):
        match = await find_youtube_match(sp_track)
        if not match:
            logger.warning(
                "No YouTube match for %r by %r", sp_track.title, sp_track.artist
            )
            unmatched.append(f"{sp_track.artist} - {sp_track.title}")
            continue
        logger.info(
            "Matched %r by %r -> %s", sp_track.title, sp_track.artist, match.get("id")
        )
        resolved.append(
            TrackInfo(
                id=match["id"],
                title=f"{sp_track.artist} - {sp_track.title}",
                duration=sp_track.duration or match.get("duration"),
                position=idx + 1,
            )
        )

    if not resolved:
        sample = ", ".join(unmatched[:3])
        raise RuntimeError(
            f"No YouTube matches found for any of {len(spotify_tracks)} tracks "
            f"(e.g. {sample}). yt-dlp search may be broken or rate-limited."
        )

    logger.info(
        "Resolved %d/%d Spotify tracks to YouTube videos",
        len(resolved),
        len(spotify_tracks),
    )

    return PlaylistInfo(
        id=f"sp_{playlist_id}",
        title="Spotify Playlist",
        tracks=resolved,
    )
