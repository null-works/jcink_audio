# CLAUDE.md - YouTube Audio Cache for Jcink

YouTube playlist to MP3 converter. FastAPI backend extracts audio via yt-dlp, uploads to Cloudflare R2, serves via embeddable HTML5 player widget for Jcink roleplay forums.

## Quick Reference

```bash
# Run tests
python3 -m pytest -v

# Run locally (requires env vars below)
uvicorn app.main:app --reload --port 8000

# Build container
docker build -t audio-cache .
```

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `R2_ENDPOINT` | Cloudflare R2 S3-compatible endpoint URL |
| `R2_BUCKET` | R2 bucket name (`imagehut-media`) |
| `R2_ACCESS_KEY` | R2 access key ID |
| `R2_SECRET_KEY` | R2 secret access key |
| `R2_PUBLIC_URL` | Public CDN domain (default: `https://media.imagehut.ch`) |
| `MAX_TRACKS` | Max tracks per playlist (default: `15`) |
| `AUDIO_BITRATE` | ffmpeg MP3 bitrate (default: `128k`) |
| `DATABASE_PATH` | SQLite file path (default: `/app/data/cache.db`) |
| `ADMIN_IPS` | Comma-separated IPs that bypass rate limits (optional) |

Tests set their own env vars in `tests/conftest.py` - no external config needed.

## Architecture

```
Jcink Forum (embed) --> audio.imagehut.ch (FastAPI) --> media.imagehut.ch (R2 CDN)
                                |
                            yt-dlp (subprocess)
```

**Flow:** Player POSTs playlist URL -> API extracts metadata via yt-dlp -> creates DB records -> background task downloads each track as 128kbps MP3 -> uploads to R2 -> player polls until complete -> audio streams from R2 CDN.

## Project Structure

```
app/
  main.py            # FastAPI app, lifespan, mounts routes + static
  config.py          # Pydantic BaseSettings (env var loading)
  database.py        # SQLite via aiosqlite, table init on startup
  models/
    playlist.py      # Pydantic schemas: Status enum, Track, Playlist
    operations.py    # All CRUD: get/create/update for playlists & tracks
  routes/
    playlist.py      # 4 endpoints (health, submit, status, track)
  services/
    youtube.py       # yt-dlp wrapper: extract_playlist_info, download_track
    storage.py       # R2/boto3: upload, delete, URL generation
    processor.py     # BackgroundTasks: process_playlist, process_track
    ratelimit.py     # In-memory IP rate limiting for refresh
static/
  player/
    player.html      # Monolithic player widget (HTML + CSS + JS in one file)
tests/
  conftest.py        # Fixtures: test DB, async client, env var setup
  test_api.py        # API integration tests
  test_database.py   # CRUD operation tests
  test_services.py   # Service layer tests (mocked externals)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns `{"status":"ok"}` |
| `POST` | `/api/playlist` | Submit YouTube playlist URL. Body: `{"url": "..."}`. Query: `?refresh=true` |
| `GET` | `/api/playlist/{id}` | Get playlist status + track list |
| `GET` | `/api/track/{id}` | Returns `{"url": "..."}` with R2 CDN link (202 if still processing) |

## Key Technical Details

### YouTube URL normalization
All playlist URLs are normalized to `https://www.youtube.com/playlist?list={id}` before passing to yt-dlp. This handles `music.youtube.com` URLs and strips tracking parameters like `&si=`. The normalization happens in `extract_playlist_info()` in `app/services/youtube.py`.

### yt-dlp JSONL parsing
`--flat-playlist --dump-json` outputs one JSON object **per line** (JSONL), NOT a single JSON with an `entries` array. Parsed line-by-line in `app/services/youtube.py`. This is a common gotcha.

### Stuck playlist recovery
The submit endpoint detects playlists stuck with 0 tracks (from interrupted extraction) and automatically cleans up the stale DB records to allow re-extraction. DB inserts use `INSERT OR REPLACE` to handle duplicate track IDs from prior failed attempts.

### Async-first design
All DB operations use `aiosqlite`. yt-dlp runs via `asyncio.create_subprocess_exec`. R2 uploads use boto3 (sync, but called from background tasks).

### Background processing
`FastAPI.BackgroundTasks` processes tracks sequentially after the initial POST returns. Tracks go through: `pending -> processing -> complete/error`. Playlist is `complete` only when ALL tracks succeed.

### R2 storage keys
Format: `audio/{playlist_id}/{track_id}.mp3`. Public URLs use custom domain (`media.imagehut.ch`) instead of presigned URLs.

### Database
SQLite with two tables: `playlists` and `tracks`. Auto-created on startup in `database.py`. Uses `aiosqlite.Row` row factory for dict-like access.

### Rate limiting (refresh)
In-memory dict tracking per-IP: 1 min cooldown between refreshes, max 3/day, blocked during processing. Resets on container restart. Admin IPs bypass via `ADMIN_IPS` env var.

### Player widget
`static/player/player.html` is a single monolithic file (HTML+CSS+JS). Config is hardcoded at lines ~87-88 (`PLAYLIST_URL`, `API_BASE`). Themeable via CSS variables on `.audio-player`.

## Conventions

- **Async everywhere** - use `async def` for route handlers and DB operations
- **Pydantic for validation** - schemas in `models/playlist.py`, settings in `config.py`
- **Status enums** - track and playlist status: `pending`, `processing`, `complete`, `error`
- **Error handling** - HTTP exceptions in routes (400/404/409/429), try-except around external calls in services
- **Tests mock externals** - yt-dlp and boto3 are mocked in tests, DB uses in-memory SQLite
- **No ORM** - raw SQL queries in `models/operations.py`

## Deployment

**VPS:** `sys.inklit.ch` (Proxmox LXC container). SSH as root.

**App location:** `~/jcink_audio` on the server (previously `/opt/youtube-cache/app`, now migrated).

**Stack:** Docker container (`audio-cache`), managed via `docker compose`. Nginx reverse proxies `audio.imagehut.ch` to container port 8942. R2 CDN at `media.imagehut.ch`. SSL via Certbot.

**SQLite data volume:** Mounted from `/opt/youtube-cache/data:/app/data` (see `docker-compose.yml`).

```bash
# Update deploy
cd ~/jcink_audio && git pull && docker build -t audio-cache . && docker rm -f audio-cache && docker compose up -d

# Verify the build picked up changes (Docker layer caching can serve stale code)
docker exec audio-cache cat /app/app/<file-to-check>
```

### Docker build caching gotcha
Docker's `COPY app/ ./app/` layer can cache stale code even after `git pull`. If `docker exec` shows old code in the container, run `docker builder prune -f` before rebuilding. Avoid `docker build --no-cache` on low-memory VPS — it rebuilds all layers (including apt-get and pip install) and can OOM the server.

### VPS recovery notes
The VPS is a Proxmox LXC container. If the server becomes unreachable after a hard reboot, use the VPS provider's web console (not SSH). The network interface is `eth0` (not `venet0`). If SSH fails from your local machine after a reboot, the host key may have changed — clear it with `ssh-keygen -R inklit.ch` and reconnect.

## Outstanding TODOs

- Remove debug button from player for production
- Make `PLAYLIST_URL` dynamic (read from Jcink custom field)
- Style player to match forum theme
- Handle multiple players on same page (unique IDs)
