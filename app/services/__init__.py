from app.services.youtube import (
    extract_playlist_id,
    extract_playlist_info,
    download_track,
    PlaylistInfo,
    TrackInfo,
)
from app.services.spotify import (
    is_spotify_url,
    extract_spotify_playlist_id,
    extract_spotify_playlist_info,
)
from app.services.storage import (
    get_r2_client,
    generate_r2_key,
    get_public_url,
    upload_file,
    delete_file,
)
from app.services.processor import (
    process_track,
    process_playlist,
)


def resolve_playlist_id(url: str) -> str | None:
    """Extract a unique playlist ID from any supported URL.

    Spotify IDs are prefixed with "sp_" to avoid collision with YouTube IDs.
    """
    if is_spotify_url(url):
        spotify_id = extract_spotify_playlist_id(url)
        return f"sp_{spotify_id}" if spotify_id else None
    return extract_playlist_id(url)


async def resolve_playlist_info(url: str) -> PlaylistInfo | None:
    """Dispatch to the right extractor based on URL type."""
    if is_spotify_url(url):
        return await extract_spotify_playlist_info(url)
    return await extract_playlist_info(url)


__all__ = [
    # YouTube
    "extract_playlist_id",
    "extract_playlist_info",
    "download_track",
    "PlaylistInfo",
    "TrackInfo",
    # Spotify
    "is_spotify_url",
    "extract_spotify_playlist_id",
    "extract_spotify_playlist_info",
    # Dispatchers
    "resolve_playlist_id",
    "resolve_playlist_info",
    # Storage
    "get_r2_client",
    "generate_r2_key",
    "get_public_url",
    "upload_file",
    "delete_file",
    # Processor
    "process_track",
    "process_playlist",
]
