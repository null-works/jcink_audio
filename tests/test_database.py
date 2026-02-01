import pytest
import aiosqlite
from app.models import (
    Status,
    get_playlist,
    create_playlist,
    update_playlist_status,
    get_tracks,
    create_track,
    update_track_complete,
    get_track,
)


class TestPlaylistOperations:
    """Test playlist CRUD operations."""

    async def test_create_playlist(self, test_db):
        """Test creating a new playlist."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            playlist = await create_playlist(
                db,
                playlist_id="PLtest123",
                url="https://youtube.com/playlist?list=PLtest123"
            )

            assert playlist is not None
            assert playlist.id == "PLtest123"
            assert playlist.status == Status.PENDING
            assert playlist.track_count == 0

    async def test_get_playlist(self, test_db):
        """Test retrieving a playlist."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            await create_playlist(db, "PLtest456", "https://youtube.com/playlist?list=PLtest456")

            playlist = await get_playlist(db, "PLtest456")
            assert playlist is not None
            assert playlist.id == "PLtest456"

    async def test_get_nonexistent_playlist(self, test_db):
        """Test retrieving a playlist that doesn't exist."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            playlist = await get_playlist(db, "PLnonexistent")
            assert playlist is None

    async def test_update_playlist_status(self, test_db):
        """Test updating playlist status."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            await create_playlist(db, "PLupdate", "https://youtube.com/playlist?list=PLupdate")

            await update_playlist_status(db, "PLupdate", Status.PROCESSING, track_count=5)

            playlist = await get_playlist(db, "PLupdate")
            assert playlist.status == Status.PROCESSING
            assert playlist.track_count == 5


class TestTrackOperations:
    """Test track CRUD operations."""

    async def test_create_track(self, test_db):
        """Test creating a new track."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            await create_playlist(db, "PLtracks", "https://youtube.com/playlist?list=PLtracks")

            track = await create_track(
                db,
                track_id="dQw4w9WgXcQ",
                playlist_id="PLtracks",
                title="Test Song",
                position=1,
                duration=212
            )

            assert track is not None
            assert track.id == "dQw4w9WgXcQ"
            assert track.title == "Test Song"
            assert track.position == 1
            assert track.status == Status.PENDING

    async def test_get_tracks(self, test_db):
        """Test retrieving all tracks for a playlist."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            await create_playlist(db, "PLmulti", "https://youtube.com/playlist?list=PLmulti")
            await create_track(db, "track1", "PLmulti", "Song 1", 1)
            await create_track(db, "track2", "PLmulti", "Song 2", 2)
            await create_track(db, "track3", "PLmulti", "Song 3", 3)

            tracks = await get_tracks(db, "PLmulti")
            assert len(tracks) == 3
            assert tracks[0].position == 1
            assert tracks[2].position == 3

    async def test_update_track_complete(self, test_db):
        """Test marking a track as complete."""
        async with aiosqlite.connect(test_db) as db:
            db.row_factory = aiosqlite.Row
            await create_playlist(db, "PLcomplete", "https://youtube.com/playlist?list=PLcomplete")
            await create_track(db, "trackdone", "PLcomplete", "Done Song", 1)

            await update_track_complete(
                db,
                track_id="trackdone",
                r2_key="audio/PLcomplete/trackdone.mp3",
                r2_url="https://r2.example.com/audio/PLcomplete/trackdone.mp3"
            )

            track = await get_track(db, "trackdone")
            assert track.status == Status.COMPLETE
            assert track.r2_key == "audio/PLcomplete/trackdone.mp3"
            assert track.r2_url is not None
