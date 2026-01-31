import os
import pytest
import tempfile
import aiosqlite
from httpx import AsyncClient, ASGITransport

# Set test environment variables before importing app
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["R2_ENDPOINT"] = "https://test.example.com"
os.environ["R2_BUCKET"] = "test-bucket"
os.environ["R2_ACCESS_KEY"] = "test-key"
os.environ["R2_SECRET_KEY"] = "test-secret"
os.environ["MAX_TRACKS"] = "10"
os.environ["AUDIO_BITRATE"] = "128k"

from app.main import app
from app.database import init_db


@pytest.fixture
async def test_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    os.environ["DATABASE_PATH"] = db_path

    # Initialize tables
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                track_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id TEXT PRIMARY KEY,
                playlist_id TEXT NOT NULL,
                title TEXT,
                duration INTEGER,
                r2_key TEXT,
                r2_url TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                position INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id)
            )
        """)
        await db.commit()

    yield db_path

    # Cleanup
    os.unlink(db_path)


@pytest.fixture
async def client(test_db):
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
