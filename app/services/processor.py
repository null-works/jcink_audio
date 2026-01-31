import os
import tempfile
import aiosqlite

from app.services.youtube import download_track
from app.services.storage import upload_file


async def process_track(
    track_id: str,
    playlist_id: str,
    db_path: str
) -> bool:
    """Process a single track: download, upload to R2, update DB.

    Args:
        track_id: YouTube video ID
        playlist_id: YouTube playlist ID
        db_path: Path to SQLite database

    Returns:
        True if successful, False otherwise
    """
    async with aiosqlite.connect(db_path) as db:
        # Update status to processing
        await db.execute(
            "UPDATE tracks SET status = 'processing' WHERE id = ?",
            (track_id,)
        )
        await db.commit()

    try:
        # Download to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            mp3_path = await download_track(track_id, temp_dir)

            if not mp3_path:
                # Download failed
                async with aiosqlite.connect(db_path) as db:
                    await db.execute(
                        "UPDATE tracks SET status = 'error' WHERE id = ?",
                        (track_id,)
                    )
                    await db.commit()
                return False

            # Upload to R2
            result = await upload_file(mp3_path, playlist_id, track_id)

            if not result:
                # Upload failed
                async with aiosqlite.connect(db_path) as db:
                    await db.execute(
                        "UPDATE tracks SET status = 'error' WHERE id = ?",
                        (track_id,)
                    )
                    await db.commit()
                return False

            r2_key, r2_url = result

            # Update database with R2 info
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """UPDATE tracks
                       SET status = 'complete', r2_key = ?, r2_url = ?
                       WHERE id = ?""",
                    (r2_key, r2_url, track_id)
                )
                await db.commit()

            return True

    except Exception:
        # Handle any unexpected errors
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE tracks SET status = 'error' WHERE id = ?",
                (track_id,)
            )
            await db.commit()
        return False


async def process_playlist(playlist_id: str, db_path: str) -> None:
    """Process all pending tracks in a playlist.

    Args:
        playlist_id: YouTube playlist ID
        db_path: Path to SQLite database
    """
    async with aiosqlite.connect(db_path) as db:
        # Update playlist status to processing
        await db.execute(
            "UPDATE playlists SET status = 'processing', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (playlist_id,)
        )
        await db.commit()

        # Get all pending tracks
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM tracks WHERE playlist_id = ? AND status = 'pending' ORDER BY position",
            (playlist_id,)
        )
        tracks = await cursor.fetchall()

    # Process each track
    all_success = True
    for track in tracks:
        success = await process_track(track["id"], playlist_id, db_path)
        if not success:
            all_success = False

    # Update playlist status
    async with aiosqlite.connect(db_path) as db:
        final_status = "complete" if all_success else "error"
        await db.execute(
            "UPDATE playlists SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (final_status, playlist_id)
        )
        await db.commit()
