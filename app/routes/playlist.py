import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse
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

router = APIRouter()


@router.post("/playlist", response_model=PlaylistResponse)
async def submit_playlist(
    data: PlaylistSubmit,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Submit a YouTube playlist URL for processing.

    If playlist is already cached, returns existing data.
    Otherwise, extracts metadata and queues for processing.
    """
    # Extract playlist ID from URL
    playlist_id = extract_playlist_id(data.url)
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube playlist URL")

    # Check if already cached
    existing = await get_playlist(db, playlist_id)
    if existing:
        tracks = await get_tracks(db, playlist_id)
        return PlaylistResponse(
            id=existing.id,
            url=existing.url,
            status=existing.status,
            track_count=existing.track_count,
            tracks=tracks,
        )

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
    """Get track audio - redirects to presigned R2 URL if ready."""
    track = await get_track(db, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if track.status != Status.COMPLETE or not track.r2_key:
        # Track not ready yet
        raise HTTPException(
            status_code=202,
            detail="Track is still processing",
            headers={"Retry-After": "5"}
        )

    # Generate presigned URL on-demand (valid for 1 hour)
    presigned_url = get_public_url(track.r2_key)
    return RedirectResponse(url=presigned_url, status_code=302)
