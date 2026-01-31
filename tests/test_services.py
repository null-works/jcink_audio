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
        """Mock yt-dlp playlist extraction response."""
        return {
            "id": "PLtest123",
            "title": "Test Playlist",
            "entries": [
                {"id": "video1", "title": "Song One", "duration": 180},
                {"id": "video2", "title": "Song Two", "duration": 240},
                {"id": "video3", "title": "Song Three", "duration": 200},
            ]
        }

    async def test_extract_playlist_info_success(self, mock_playlist_response):
        """Test successful playlist extraction."""
        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(mock_playlist_response).encode(),
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
        # Add more tracks to exceed limit
        mock_playlist_response["entries"] = [
            {"id": f"video{i}", "title": f"Song {i}", "duration": 180}
            for i in range(15)
        ]

        with patch("app.services.youtube.asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                json.dumps(mock_playlist_response).encode(),
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
        """Test public URL generation."""
        from app.services.storage import get_public_url

        url = get_public_url("audio/PLtest123/videoABC.mp3")
        assert "audio/PLtest123/videoABC.mp3" in url
        assert url.startswith("https://")

    async def test_upload_file_success(self, tmp_path):
        """Test successful file upload."""
        from app.services.storage import upload_file

        # Create a fake MP3 file
        fake_mp3 = tmp_path / "test.mp3"
        fake_mp3.write_bytes(b"fake mp3 content")

        with patch("app.services.storage.get_r2_client") as mock_client:
            mock_s3 = MagicMock()
            mock_client.return_value = mock_s3

            r2_key, r2_url = await upload_file(str(fake_mp3), "PLtest123", "videoABC")

            assert r2_key == "audio/PLtest123/videoABC.mp3"
            assert "audio/PLtest123/videoABC.mp3" in r2_url
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
