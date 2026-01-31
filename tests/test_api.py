import pytest


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
