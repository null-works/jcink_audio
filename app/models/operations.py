import aiosqlite
from app.models.playlist import Playlist, Track, Status


async def get_playlist(db: aiosqlite.Connection, playlist_id: str) -> Playlist | None:
    """Get playlist by ID."""
    cursor = await db.execute(
        "SELECT * FROM playlists WHERE id = ?",
        (playlist_id,)
    )
    row = await cursor.fetchone()
    if row:
        return Playlist(**dict(row))
    return None


async def create_playlist(db: aiosqlite.Connection, playlist_id: str, url: str) -> Playlist:
    """Create a new playlist."""
    await db.execute(
        "INSERT OR IGNORE INTO playlists (id, url, status) VALUES (?, ?, ?)",
        (playlist_id, url, Status.PENDING.value)
    )
    await db.commit()
    return await get_playlist(db, playlist_id)


async def update_playlist_status(
    db: aiosqlite.Connection,
    playlist_id: str,
    status: Status,
    track_count: int | None = None
):
    """Update playlist status."""
    if track_count is not None:
        await db.execute(
            """UPDATE playlists
               SET status = ?, track_count = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (status.value, track_count, playlist_id)
        )
    else:
        await db.execute(
            "UPDATE playlists SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status.value, playlist_id)
        )
    await db.commit()


async def get_tracks(db: aiosqlite.Connection, playlist_id: str) -> list[Track]:
    """Get all tracks for a playlist."""
    cursor = await db.execute(
        "SELECT * FROM tracks WHERE playlist_id = ? ORDER BY position",
        (playlist_id,)
    )
    rows = await cursor.fetchall()
    return [Track(**dict(row)) for row in rows]


async def create_track(
    db: aiosqlite.Connection,
    track_id: str,
    playlist_id: str,
    title: str,
    position: int,
    duration: int | None = None
) -> Track:
    """Create a new track."""
    await db.execute(
        """INSERT OR IGNORE INTO tracks (id, playlist_id, title, duration, position, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (track_id, playlist_id, title, duration, position, Status.PENDING.value)
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
    row = await cursor.fetchone()
    return Track(**dict(row))


async def update_track_complete(
    db: aiosqlite.Connection,
    track_id: str,
    r2_key: str,
    r2_url: str
):
    """Mark track as complete with R2 URL."""
    await db.execute(
        """UPDATE tracks
           SET status = ?, r2_key = ?, r2_url = ?
           WHERE id = ?""",
        (Status.COMPLETE.value, r2_key, r2_url, track_id)
    )
    await db.commit()


async def update_track_error(db: aiosqlite.Connection, track_id: str):
    """Mark track as error."""
    await db.execute(
        "UPDATE tracks SET status = ? WHERE id = ?",
        (Status.ERROR.value, track_id)
    )
    await db.commit()


async def get_track(db: aiosqlite.Connection, track_id: str) -> Track | None:
    """Get track by ID."""
    cursor = await db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
    row = await cursor.fetchone()
    if row:
        return Track(**dict(row))
    return None
