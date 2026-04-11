import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Mock environment before importing
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["R2_ENDPOINT"] = "https://test.example.com"
os.environ["R2_BUCKET"] = "test-bucket"
os.environ["R2_ACCESS_KEY"] = "test-key"
os.environ["R2_SECRET_KEY"] = "test-secret"
os.environ["MAX_TRACKS"] = "10"
os.environ["SPOTIFY_CLIENT_ID"] = "test-client-id"
os.environ["SPOTIFY_CLIENT_SECRET"] = "test-client-secret"

from app.services.spotify import (
    is_spotify_url,
    extract_spotify_playlist_id,
    extract_spotify_playlist_info,
    find_youtube_match,
    _score_candidate,
    SpotifyTrack,
)


class TestIsSpotifyUrl:
    def test_https_spotify_url(self):
        assert is_spotify_url("https://open.spotify.com/playlist/abc123")

    def test_https_spotify_url_with_si(self):
        assert is_spotify_url("https://open.spotify.com/playlist/abc123?si=xyz")

    def test_spotify_uri(self):
        assert is_spotify_url("spotify:playlist:abc123")

    def test_youtube_url_is_not_spotify(self):
        assert not is_spotify_url("https://www.youtube.com/playlist?list=PLxxx")

    def test_empty_string(self):
        assert not is_spotify_url("")

    def test_random_text(self):
        assert not is_spotify_url("hello world")


class TestExtractSpotifyPlaylistId:
    def test_https_url(self):
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        assert extract_spotify_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_https_url_with_si(self):
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=xyz123"
        assert extract_spotify_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_spotify_uri(self):
        url = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
        assert extract_spotify_playlist_id(url) == "37i9dQZF1DXcBWIGoYBM5M"

    def test_invalid_url(self):
        assert extract_spotify_playlist_id("https://youtube.com/watch?v=abc") is None


class TestScoreCandidate:
    def test_perfect_match_wins(self):
        entry = {
            "id": "vid1",
            "title": "Artist Name - Song Title (Official Audio)",
            "duration": 180,
        }
        score = _score_candidate(entry, "Song Title", "Artist Name", 180)
        assert score > 0

    def test_wrong_duration_rejected(self):
        entry = {"id": "vid1", "title": "Song Title", "duration": 300}
        score = _score_candidate(entry, "Song Title", "Artist", 180)
        assert score == float("-inf")

    def test_karaoke_penalized(self):
        good = {"id": "v1", "title": "Artist - Song", "duration": 180}
        karaoke = {"id": "v2", "title": "Song (Karaoke Version)", "duration": 180}
        good_score = _score_candidate(good, "Song", "Artist", 180)
        karaoke_score = _score_candidate(karaoke, "Song", "Artist", 180)
        assert good_score > karaoke_score

    def test_live_version_penalized_when_studio_requested(self):
        studio = {"id": "v1", "title": "Artist - Song (Official)", "duration": 180}
        live = {"id": "v2", "title": "Artist - Song (Live at Wembley)", "duration": 180}
        assert _score_candidate(studio, "Song", "Artist", 180) > _score_candidate(
            live, "Song", "Artist", 180
        )

    def test_live_not_penalized_when_target_is_live(self):
        # If the Spotify track itself has "live" in the title, don't penalize matches
        entry = {"id": "v1", "title": "Artist - Song (Live)", "duration": 180}
        score = _score_candidate(entry, "Song (Live)", "Artist", 180)
        # Should be positive since "live" is in both
        assert score > 0

    def test_duration_tolerance(self):
        # Within tolerance should score
        entry = {"id": "v1", "title": "Song", "duration": 185}
        assert _score_candidate(entry, "Song", "Artist", 180) > float("-inf")
        # Outside tolerance should reject
        entry2 = {"id": "v2", "title": "Song", "duration": 200}
        assert _score_candidate(entry2, "Song", "Artist", 180) == float("-inf")


class TestFindYoutubeMatch:
    async def test_picks_best_match_from_candidates(self):
        track = SpotifyTrack(title="Song Title", artist="Artist Name", duration=180)

        fake_stdout = (
            b'{"id": "bad1", "title": "Song Title (Karaoke)", "duration": 180}\n'
            b'{"id": "good", "title": "Artist Name - Song Title (Official)", "duration": 180}\n'
            b'{"id": "bad2", "title": "Song Title (Cover)", "duration": 180}\n'
        )

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(fake_stdout, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            result = await find_youtube_match(track)

        assert result is not None
        assert result["id"] == "good"

    async def test_returns_none_when_no_candidates(self):
        track = SpotifyTrack(title="X", artist="Y", duration=180)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            result = await find_youtube_match(track)

        assert result is None

    async def test_returns_none_when_all_candidates_fail_duration(self):
        track = SpotifyTrack(title="Song", artist="Artist", duration=180)

        # All candidates have wildly wrong durations
        fake_stdout = (
            b'{"id": "v1", "title": "Song", "duration": 400}\n'
            b'{"id": "v2", "title": "Song", "duration": 500}\n'
        )

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(fake_stdout, b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_proc
            result = await find_youtube_match(track)

        assert result is None


class TestExtractSpotifyPlaylistInfo:
    async def test_success_resolves_tracks(self):
        spotify_tracks = [
            SpotifyTrack(title="Song A", artist="Artist 1", duration=180),
            SpotifyTrack(title="Song B", artist="Artist 2", duration=200),
        ]

        async def fake_match(track):
            return {"id": f"yt_{track.title.replace(' ', '_')}", "duration": track.duration}

        with patch(
            "app.services.spotify.get_spotify_playlist_tracks",
            new_callable=AsyncMock,
        ) as mock_fetch, patch(
            "app.services.spotify.find_youtube_match",
            new=fake_match,
        ):
            mock_fetch.return_value = spotify_tracks
            result = await extract_spotify_playlist_info(
                "https://open.spotify.com/playlist/abc123"
            )

        assert result is not None
        assert result.id == "sp_abc123"
        assert len(result.tracks) == 2
        assert result.tracks[0].id == "yt_Song_A"
        assert result.tracks[0].title == "Artist 1 - Song A"

    async def test_skips_unmatched_tracks(self):
        spotify_tracks = [
            SpotifyTrack(title="Found", artist="A", duration=180),
            SpotifyTrack(title="Missing", artist="B", duration=200),
        ]

        async def fake_match(track):
            if track.title == "Missing":
                return None
            return {"id": "yt_found", "duration": 180}

        with patch(
            "app.services.spotify.get_spotify_playlist_tracks",
            new_callable=AsyncMock,
        ) as mock_fetch, patch(
            "app.services.spotify.find_youtube_match",
            new=fake_match,
        ):
            mock_fetch.return_value = spotify_tracks
            result = await extract_spotify_playlist_info(
                "https://open.spotify.com/playlist/abc123"
            )

        assert result is not None
        assert len(result.tracks) == 1
        assert result.tracks[0].id == "yt_found"

    async def test_returns_none_if_empty_playlist(self):
        with patch(
            "app.services.spotify.get_spotify_playlist_tracks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = await extract_spotify_playlist_info(
                "https://open.spotify.com/playlist/abc123"
            )
        assert result is None

    async def test_returns_none_on_fetch_error(self):
        with patch(
            "app.services.spotify.get_spotify_playlist_tracks",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.side_effect = Exception("API error")
            result = await extract_spotify_playlist_info(
                "https://open.spotify.com/playlist/abc123"
            )
        assert result is None

    async def test_respects_max_tracks_limit(self):
        from app.config import settings

        # Create more tracks than the limit
        many = [
            SpotifyTrack(title=f"Song {i}", artist="A", duration=180)
            for i in range(settings.max_tracks + 5)
        ]

        async def fake_match(track):
            return {"id": f"yt_{track.title}", "duration": 180}

        with patch(
            "app.services.spotify.get_spotify_playlist_tracks",
            new_callable=AsyncMock,
        ) as mock_fetch, patch(
            "app.services.spotify.find_youtube_match",
            new=fake_match,
        ):
            mock_fetch.return_value = many
            result = await extract_spotify_playlist_info(
                "https://open.spotify.com/playlist/abc"
            )

        assert result is not None
        assert len(result.tracks) == settings.max_tracks
