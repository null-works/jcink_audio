import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
import aiosqlite

from app.database import get_db
from app.config import settings
from app.models import (
    Status,
    PlaylistSubmit,
    PlaylistResponse,
    Track,
    get_playlist,
    create_playlist,
    get_tracks,
    create_track,
    get_track,
)
from app.services import extract_playlist_id, extract_playlist_info, process_playlist
from app.services.storage import get_public_url
from app.services.ratelimit import check_refresh_allowed, record_refresh

router = APIRouter()


@router.post("/playlist", response_model=PlaylistResponse)
async def submit_playlist(
    data: PlaylistSubmit,
    request: Request,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db),
    refresh: bool = False
):
    """Submit a YouTube playlist URL for processing.

    If playlist is already cached, returns existing data.
    Otherwise, extracts metadata and queues for processing.
    Use ?refresh=true to force re-fetch from YouTube.
    """
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Extract playlist ID from URL
    playlist_id = extract_playlist_id(data.url)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube playlist URL")

    # Check if already cached
    existing = await get_playlist(db, playlist_id)
    existing_tracks = await get_tracks(db, playlist_id) if existing else []

    # Detect stuck/broken state: playlist exists but has no tracks and is not actively processing
    # This can happen if extraction succeeded but track creation was interrupted
    is_broken = (
        existing
        and len(existing_tracks) == 0
        and existing.status not in (Status.PENDING, Status.PROCESSING)
    )

    if existing and not refresh and not is_broken:
        return PlaylistResponse(
            id=existing.id,
            url=existing.url,
            status=existing.status,
            track_count=existing.track_count,
            tracks=existing_tracks,
        )

    # If broken, clean up the stale record so we can re-create it below
    if is_broken:
        await db.execute("DELETE FROM tracks WHERE playlist_id = ?", (playlist_id,))
        await db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        await db.commit()
        existing = None

    # If refresh requested, apply rate limiting and status checks
    if refresh and existing:
        # Check rate limits
        allowed, reason = check_refresh_allowed(client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)

        # Check if playlist is still processing (rule 2)
        if existing.status in (Status.PENDING, Status.PROCESSING):
            raise HTTPException(
                status_code=409,
                detail="Playlist is still processing. Wait for completion before refreshing."
            )

    # If refresh requested and playlist exists, delete old data
    if existing and refresh:
        from app.services.storage import delete_file
        # Delete old tracks from R2 and DB
        old_tracks = await get_tracks(db, playlist_id)
        for track in old_tracks:
            if track.r2_key:
                try:
                    await delete_file(track.r2_key)
                except Exception:
                    pass  # Ignore R2 deletion errors
        await db.execute("DELETE FROM tracks WHERE playlist_id = ?", (playlist_id,))
        await db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        await db.commit()

        # Record successful refresh for rate limiting
        record_refresh(client_ip)

    # Extract playlist info from YouTube
    playlist_info = await extract_playlist_info(data.url)
    if not playlist_info:
        raise HTTPException(status_code=400, detail="Failed to extract playlist info")

    # Create playlist record
    playlist = await create_playlist(db, playlist_id, data.url)

    # Create track records
    tracks = []
    for track_info in playlist_info.tracks:
        track = await create_track(
            db,
            track_id=track_info.id,
            playlist_id=playlist_id,
            title=track_info.title,
            position=track_info.position,
            duration=track_info.duration,
        )
        tracks.append(track)

    # Update playlist track count
    await db.execute(
        "UPDATE playlists SET track_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (len(tracks), playlist_id)
    )
    await db.commit()

    # Queue background processing task
    background_tasks.add_task(process_playlist, playlist_id, settings.database_path)

    return PlaylistResponse(
        id=playlist_id,
        url=data.url,
        status=Status.PENDING,
        track_count=len(tracks),
        tracks=tracks,
    )


@router.get("/playlist/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist_status(
    playlist_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get playlist status and track information."""
    playlist = await get_playlist(db, playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    tracks = await get_tracks(db, playlist_id)

    return PlaylistResponse(
        id=playlist.id,
        url=playlist.url,
        status=playlist.status,
        track_count=playlist.track_count,
        tracks=tracks,
    )


@router.get("/track/{track_id}")
async def get_track_audio(
    track_id: str,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get track audio URL - returns direct R2 URL for CORS compatibility."""
    track = await get_track(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if track.status != Status.COMPLETE or not track.r2_key:
        raise HTTPException(
            status_code=202,
            detail="Track is still processing",
            headers={"Retry-After": "5"}
        )

    # Return direct URL instead of redirect (better CORS support for Web Audio API)
    public_url = get_public_url(track.r2_key)
    return {"url": public_url}
