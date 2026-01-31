import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import json


class TestHealthEndpoint:
    """Test health check endpoint."""

    async def test_health_returns_ok(self, client):
        """Test that health endpoint returns ok status."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestStaticFiles:
    """Test static file serving."""

    async def test_static_route_exists(self, client):
        """Test that static route is mounted (404 for missing file is expected)."""
        response = await client.get("/static/nonexistent.js")
        # 404 means route exists but file doesn't - that's correct
        assert response.status_code == 404


class TestPlaylistEndpoints:
    """Test playlist API endpoints."""

    @pytest.fixture
    def mock_playlist_info(self):
        """Mock playlist info from yt-dlp."""
        from app.services.youtube import PlaylistInfo, TrackInfo
        return PlaylistInfo(
            id="PLtest123",
            title="Test Playlist",
            tracks=[
                TrackInfo(id="video1", title="Song One", duration=180, position=1),
                TrackInfo(id="video2", title="Song Two", duration=240, position=2),
            ]
        )

    async def test_submit_playlist_success(self, client, test_db, mock_playlist_info):
        """Test successful playlist submission."""
        with patch("app.routes.playlist.extract_playlist_info", new_callable=AsyncMock) as mock_extract, \
             patch("app.routes.playlist.process_playlist", new_callable=AsyncMock) as mock_process:
            mock_extract.return_value = mock_playlist_info

            response = await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLtest123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "PLtest123"
            assert data["status"] == "pending"
            assert len(data["tracks"]) == 2

    async def test_submit_playlist_invalid_url(self, client, test_db):
        """Test submission with invalid URL."""
        response = await client.post(
            "/api/playlist",
            json={"url": "not a valid url"}
        )

        assert response.status_code == 400

    async def test_submit_playlist_extraction_failed(self, client, test_db):
        """Test handling of yt-dlp extraction failure."""
        with patch("app.routes.playlist.extract_playlist_info", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = None

            response = await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLbad"}
            )

            assert response.status_code == 400

    async def test_submit_playlist_returns_cached(self, client, test_db, mock_playlist_info):
        """Test that cached playlist is returned without re-processing."""
        with patch("app.routes.playlist.extract_playlist_info", new_callable=AsyncMock) as mock_extract, \
             patch("app.routes.playlist.process_playlist", new_callable=AsyncMock):
            mock_extract.return_value = mock_playlist_info

            # First submission
            response1 = await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLtest123"}
            )
            assert response1.status_code == 200

            # Second submission - should return cached
            response2 = await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLtest123"}
            )
            assert response2.status_code == 200
            assert response2.json()["id"] == "PLtest123"

            # extract_playlist_info should only be called once (first time)
            assert mock_extract.call_count == 1

    async def test_get_playlist_success(self, client, test_db, mock_playlist_info):
        """Test getting playlist by ID."""
        with patch("app.routes.playlist.extract_playlist_info", new_callable=AsyncMock) as mock_extract, \
             patch("app.routes.playlist.process_playlist", new_callable=AsyncMock):
            mock_extract.return_value = mock_playlist_info

            # Create playlist first
            await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLtest123"}
            )

            # Get playlist
            response = await client.get("/api/playlist/PLtest123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "PLtest123"
            assert len(data["tracks"]) == 2

    async def test_get_playlist_not_found(self, client, test_db):
        """Test getting non-existent playlist."""
        response = await client.get("/api/playlist/PLnonexistent")

        assert response.status_code == 404

    async def test_get_track_redirect(self, client, test_db, mock_playlist_info):
        """Test track redirect to presigned R2 URL."""
        with patch("app.routes.playlist.extract_playlist_info", new_callable=AsyncMock) as mock_extract, \
             patch("app.routes.playlist.process_playlist", new_callable=AsyncMock), \
             patch("app.routes.playlist.get_public_url") as mock_presign:
            mock_extract.return_value = mock_playlist_info
            mock_presign.return_value = "https://r2.example.com/presigned/audio/test.mp3?token=abc"

            # Create playlist
            await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLtest123"}
            )

            # Manually update track with R2 key for testing
            import aiosqlite
            async with aiosqlite.connect(test_db) as db:
                await db.execute(
                    "UPDATE tracks SET status='complete', r2_key='audio/PLtest123/video1.mp3' WHERE id='video1'"
                )
                await db.commit()

            # Get track - should redirect to presigned URL
            response = await client.get("/api/track/video1", follow_redirects=False)

            assert response.status_code == 302
            assert "presigned" in response.headers["location"]

    async def test_get_track_not_ready(self, client, test_db, mock_playlist_info):
        """Test getting track that hasn't been processed yet."""
        with patch("app.routes.playlist.extract_playlist_info", new_callable=AsyncMock) as mock_extract, \
             patch("app.routes.playlist.process_playlist", new_callable=AsyncMock):
            mock_extract.return_value = mock_playlist_info

            # Create playlist (tracks will be pending)
            await client.post(
                "/api/playlist",
                json={"url": "https://youtube.com/playlist?list=PLtest123"}
            )

            # Get track - should return 202 (accepted but not ready)
            response = await client.get("/api/track/video1")

            assert response.status_code == 202

    async def test_get_track_not_found(self, client, test_db):
        """Test getting non-existent track."""
        response = await client.get("/api/track/nonexistent")

        assert response.status_code == 404
