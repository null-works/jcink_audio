import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import os

# Mock environment before importing
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["R2_ENDPOINT"] = "https://test.example.com"
os.environ["R2_BUCKET"] = "test-bucket"
os.environ["R2_ACCESS_KEY"] = "test-key"
os.environ["R2_SECRET_KEY"] = "test-secret"
os.environ["MAX_TRACKS"] = "10"
os.environ["AUDIO_BITRATE"] = "128k"

from app.services.youtube import (
    extract_playlist_id,
    extract_playlist_info,
    download_track,
    PlaylistInfo,
    TrackInfo,
)
from app.config import settings


class TestExtractPlaylistId:
    """Test YouTube playlist ID extraction from URLs."""

    def test_extract_from_standard_url(self):
        """Test extracting ID from standard playlist URL."""
        url = "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        assert extract_playlist_id(url) == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    def test_extract_from_short_url(self):
        """Test extracting ID from URL with video and list param."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
        assert extract_playlist_id(url) == "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"

    def test_extract_from_music_url(self):
        """Test extracting ID from YouTube Music URL."""
        url = "https://music.youtube.com/playlist?list=PLtest123"
        assert extract_playlist_id(url) == "PLtest123"

    def test_invalid_url_returns_none(self):
        """Test that invalid URLs return None."""
        assert extract_playlist_id("https://youtube.com/watch?v=abc") is None
        assert extract_playlist_id("not a url") is None


class TestExtractPlaylistInfo:
    """Test playlist metadata extraction."""

    @pytest.fixture
    def mock_playlist_response(self):
        """Mock yt-dlp playlist extraction response (JSONL format)."""
        # yt-dlp outputs one JSON object per line
        entries = [
            {"id": "video1", "title": "Song One", "duration": 180, "playlist_title": "Test Playlist"},
            {"id": "video2", "title": "Song Two", "duration": 240, "playlist_title": "Test Playlist"},
            {"id": "video3", "title": "Song Three", "duration": 200, "playlist_title": "Test Playlist"},
        ]
        return "\n".join(json.dumps(e) for e in entries)

    async def test_extract_playlist_info_success(self, mock_playlist_response):
        """Test successful playlist extraction."""
        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                mock_playlist_response.encode(),
                b""
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await extract_playlist_info("https://youtube.com/playlist?list=PLtest123")

            assert result is not None
            assert result.id == "PLtest123"
            assert result.title == "Test Playlist"
            assert len(result.tracks) == 3
            assert result.tracks[0].id == "video1"
            assert result.tracks[0].title == "Song One"
            assert result.tracks[0].duration == 180

    async def test_extract_playlist_enforces_max_tracks(self, mock_playlist_response):
        """Test that playlist extraction respects MAX_TRACKS limit."""
        # Create 15 tracks in JSONL format
        entries = [
            {"id": f"video{i}", "title": f"Song {i}", "duration": 180, "playlist_title": "Test Playlist"}
            for i in range(15)
        ]
        jsonl_response = "\n".join(json.dumps(e) for e in entries)

        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                jsonl_response.encode(),
                b""
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await extract_playlist_info("https://youtube.com/playlist?list=PLtest123")

            # Should be limited to MAX_TRACKS (10)
            assert len(result.tracks) == settings.max_tracks

    async def test_extract_playlist_handles_error(self):
        """Test handling of yt-dlp errors."""
        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"ERROR: Playlist not found")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await extract_playlist_info("https://youtube.com/playlist?list=PLbad")

            assert result is None


class TestDownloadTrack:
    """Test audio download functionality."""

    async def test_download_track_success(self, tmp_path):
        """Test successful track download."""
        output_dir = tmp_path / "downloads"
        output_dir.mkdir()

        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # Create a fake output file that yt-dlp would create
            fake_mp3 = output_dir / "testvideo.mp3"
            fake_mp3.write_bytes(b"fake mp3 content")

            result = await download_track("testvideo", str(output_dir))

            assert result is not None
            assert "testvideo" in result

    async def test_download_track_failure(self, tmp_path):
        """Test handling of download failure."""
        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"ERROR: Video unavailable")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            result = await download_track("badvideo", str(tmp_path))

            assert result is None


class TestR2Storage:
    """Test R2 storage operations."""

    def test_get_r2_client(self):
        """Test R2 client creation."""
        from app.services.storage import get_r2_client

        client = get_r2_client()
        assert client is not None

    def test_generate_r2_key(self):
        """Test R2 key generation."""
        from app.services.storage import generate_r2_key

        key = generate_r2_key("PLtest123", "videoABC")
        assert key == "audio/PLtest123/videoABC.mp3"

    def test_get_public_url(self):
        """Test presigned URL generation."""
        from app.services.storage import get_public_url

        with patch("app.services.storage.get_r2_client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://r2.example.com/presigned?token=abc"
            mock_client.return_value = mock_s3

            url = get_public_url("audio/PLtest123/videoABC.mp3")
            assert url.startswith("https://")
            mock_s3.generate_presigned_url.assert_called_once()

    async def test_upload_file_success(self, tmp_path):
        """Test successful file upload."""
        from app.services.storage import upload_file

        # Create a fake MP3 file
        fake_mp3 = tmp_path / "test.mp3"
        fake_mp3.write_bytes(b"fake mp3 content")

        with patch("app.services.storage.get_r2_client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://r2.example.com/presigned?token=abc"
            mock_client.return_value = mock_s3

            r2_key, r2_url = await upload_file(str(fake_mp3), "PLtest123", "videoABC")

            assert r2_key == "audio/PLtest123/videoABC.mp3"
            assert r2_url.startswith("https://")
            mock_s3.upload_file.assert_called_once()

    async def test_upload_file_failure(self, tmp_path):
        """Test upload failure handling."""
        from app.services.storage import upload_file
        from botocore.exceptions import ClientError

        fake_mp3 = tmp_path / "test.mp3"
        fake_mp3.write_bytes(b"fake mp3 content")

        with patch("app.services.storage.get_r2_client") as mock_client:
            mock_s3 = MagicMock()
            mock_s3.upload_file.side_effect = ClientError(
                {"Error": {"Code": "500", "Message": "Internal Error"}},
                "upload_file"
            )
            mock_client.return_value = mock_s3

            result = await upload_file(str(fake_mp3), "PLtest123", "videoABC")

            assert result is None

    async def test_delete_file(self):
        """Test file deletion."""
        from app.services.storage import delete_file

        with patch("app.services.storage.get_r2_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            await delete_file("audio/PLtest123/videoABC.mp3")

            mock_s3.delete_object.assert_called_once()


class TestBackgroundProcessor:
    """Test background processing functionality."""

    @pytest.fixture
    async def processor_db(self, tmp_path):
        """Create a test database with playlist and tracks."""
        import aiosqlite

        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("""
                CREATE TABLE playlists (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    track_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE tracks (
                    id TEXT PRIMARY KEY,
                    playlist_id TEXT NOT NULL,
                    title TEXT,
                    duration INTEGER,
                    r2_key TEXT,
                    r2_url TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    position INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Insert test data
            await db.execute(
                "INSERT INTO playlists (id, url, status, track_count) VALUES (?, ?, ?, ?)",
                ("PLtest", "https://youtube.com/playlist?list=PLtest", "pending", 2)
            )
            await db.execute(
                "INSERT INTO tracks (id, playlist_id, title, position, status) VALUES (?, ?, ?, ?, ?)",
                ("track1", "PLtest", "Song One", 1, "pending")
            )
            await db.execute(
                "INSERT INTO tracks (id, playlist_id, title, position, status) VALUES (?, ?, ?, ?, ?)",
                ("track2", "PLtest", "Song Two", 2, "pending")
            )
            await db.commit()

        return str(db_path)

    async def test_process_track_success(self, processor_db, tmp_path):
        """Test successful track processing."""
        from app.services.processor import process_track

        with patch("app.services.processor.download_track", new_callable=AsyncMock) as mock_download, \
             patch("app.services.processor.upload_file", new_callable=AsyncMock) as mock_upload:

            # Mock successful download
            fake_mp3 = tmp_path / "track1.mp3"
            fake_mp3.write_bytes(b"fake mp3")
            mock_download.return_value = str(fake_mp3)

            # Mock successful upload
            mock_upload.return_value = ("audio/PLtest/track1.mp3", "https://r2.example.com/audio/PLtest/track1.mp3")

            result = await process_track("track1", "PLtest", processor_db)

            assert result is True
            mock_download.assert_called_once()
            mock_upload.assert_called_once()

    async def test_process_track_download_failure(self, processor_db):
        """Test track processing when download fails."""
        from app.services.processor import process_track

        with patch("app.services.processor.download_track", new_callable=AsyncMock) as mock_download:
            mock_download.return_value = None

            result = await process_track("track1", "PLtest", processor_db)

            assert result is False

    async def test_process_playlist_success(self, processor_db, tmp_path):
        """Test processing entire playlist."""
        from app.services.processor import process_playlist
        import aiosqlite

        with patch("app.services.processor.download_track", new_callable=AsyncMock) as mock_download, \
             patch("app.services.processor.upload_file", new_callable=AsyncMock) as mock_upload:

            # Mock downloads
            fake_mp3 = tmp_path / "track.mp3"
            fake_mp3.write_bytes(b"fake mp3")
            mock_download.return_value = str(fake_mp3)

            # Mock uploads
            mock_upload.return_value = ("audio/PLtest/track.mp3", "https://r2.example.com/audio/PLtest/track.mp3")

            await process_playlist("PLtest", processor_db)

            # Verify playlist status is complete
            async with aiosqlite.connect(processor_db) as db:
                cursor = await db.execute("SELECT status FROM playlists WHERE id = ?", ("PLtest",))
                row = await cursor.fetchone()
                assert row[0] == "complete"

                # Verify all tracks are complete
                cursor = await db.execute("SELECT status FROM tracks WHERE playlist_id = ?", ("PLtest",))
                rows = await cursor.fetchall()
                assert all(row[0] == "complete" for row in rows)
