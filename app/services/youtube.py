import asyncio
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from app.config import settings


@dataclass
class TrackInfo:
    """Metadata for a single track."""
    id: str
    title: str
    duration: int | None = None
    position: int = 0


@dataclass
class PlaylistInfo:
    """Metadata for a playlist."""
    id: str
    title: str
    tracks: list[TrackInfo]


def extract_playlist_id(url: str) -> str | None:
    """Extract playlist ID from a YouTube URL.

    Supports:
    - https://www.youtube.com/playlist?list=PLxxxxx
    - https://www.youtube.com/watch?v=xxx&list=PLxxxxx
    - https://music.youtube.com/playlist?list=PLxxxxx
    """
    try:
        parsed = urlparse(url)
        if "youtube.com" not in parsed.netloc and "youtu.be" not in parsed.netloc:
            return None

        query_params = parse_qs(parsed.query)
        playlist_id = query_params.get("list", [None])[0]

        return playlist_id
    except Exception:
        return None


async def extract_playlist_info(url: str) -> PlaylistInfo | None:
    """Extract playlist metadata using yt-dlp.

    Returns playlist info with tracks limited to MAX_TRACKS.
    Returns None if extraction fails.
    """
    playlist_id = extract_playlist_id(url)
    if not playlist_id:
        return None

    try:
        # Use yt-dlp to get playlist metadata without downloading
        process = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            "--no-warnings",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return None

        # yt-dlp outputs one JSON object per line (JSONL format)
        lines = stdout.decode().strip().split('\n')
        entries = []
        playlist_title = "Unknown Playlist"

        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
                # Get playlist title from first entry
                if len(entries) == 1:
                    playlist_title = entry.get("playlist_title", "Unknown Playlist")
            except json.JSONDecodeError:
                continue

        # Limit to MAX_TRACKS
        entries = entries[:settings.max_tracks]

        tracks = [
            TrackInfo(
                id=entry.get("id", ""),
                title=entry.get("title", "Unknown"),
                duration=entry.get("duration"),
                position=idx + 1,
            )
            for idx, entry in enumerate(entries)
            if entry.get("id")
        ]

        if not tracks:
            return None

        return PlaylistInfo(
            id=playlist_id,
            title=playlist_title,
            tracks=tracks,
        )

    except Exception:
        return None


async def download_track(video_id: str, output_dir: str) -> str | None:
    """Download a single track as MP3.

    Args:
        video_id: YouTube video ID
        output_dir: Directory to save the MP3 file

    Returns:
        Path to the downloaded MP3 file, or None if download failed.
    """
    output_template = os.path.join(output_dir, f"{video_id}.%(ext)s")
    expected_output = os.path.join(output_dir, f"{video_id}.mp3")

    try:
        process = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-x",  # Extract audio
            "--audio-format", "mp3",
            "--audio-quality", settings.audio_bitrate,
            "--no-playlist",
            "--no-warnings",
            "-o", output_template,
            f"https://www.youtube.com/watch?v={video_id}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return None

        # Check if the file was created
        if os.path.exists(expected_output):
            return expected_output

        return None

    except Exception:
        return None
