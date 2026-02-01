# YouTube Audio Cache for Jcink Roleplay Forum

## Project Status: COMPLETE ✅

Fully functional YouTube playlist to MP3 converter. Server extracts audio via yt-dlp → uploads to Cloudflare R2 → serves via embeddable HTML5 player widget.

## Live URLs

| Service | URL |
|---------|-----|
| API | `https://audio.imagehut.ch` |
| Audio CDN | `https://media.imagehut.ch` |
| Player | `https://audio.imagehut.ch/static/player/player.html` |
| Health Check | `https://audio.imagehut.ch/health` |

## Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│  Jcink Forum    │────▶│  audio.imagehut.ch   │────▶│  media.imagehut.ch │
│  (embed widget) │     │  (FastAPI on VPS)    │     │  (R2 CDN)          │
└─────────────────┘     └──────────────────────┘     └───────────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   yt-dlp     │
                        │  (subprocess)│
                        └──────────────┘
```

**Data flow:**
1. Player JS posts YouTube playlist URL to `/api/playlist`
2. API extracts metadata via yt-dlp, creates DB records
3. Background task downloads each track, converts to 128kbps MP3
4. Uploads to R2 at `audio/{playlist_id}/{track_id}.mp3`
5. Player polls `/api/playlist/{id}` until tracks complete
6. Audio plays via `/api/track/{id}` which redirects to R2 CDN

## Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| VPS | ✅ | Ubuntu + Portainer at `sys.inklit.ch` |
| API Domain | ✅ | `audio.imagehut.ch` → nginx → port 8942 |
| CDN Domain | ✅ | `media.imagehut.ch` → R2 custom domain |
| SSL | ✅ | Certbot/Let's Encrypt |
| R2 Bucket | ✅ | `imagehut-media` on Cloudflare |
| Container | ✅ | `audio-cache` via Portainer |

## R2 Credentials

```
Endpoint: https://5215ebbf6291827b415632f0cd0eae79.r2.cloudflarestorage.com
Bucket: imagehut-media
Public URL: https://media.imagehut.ch
Access Key: b6cf7481eae8fddbd2abfd9762246606
Secret Key: 5047f0a7f482f2347b442eefa06aad455cd5e5e7f70c6a730d5c163f95e34386
```

## Constraints

- **Max 10 songs per playlist** (server-enforced via `MAX_TRACKS`)
- **128kbps MP3** (~3.5MB per song, ~1MB/min)
- **~35MB per character** (10 songs × 3.5MB)
- **R2 free tier**: 10GB storage, zero egress

## Project Structure

```
jcink_audio/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, mounts routes + static
│   ├── config.py            # Pydantic settings from env vars
│   ├── database.py          # SQLite async connection + init
│   ├── models/
│   │   ├── __init__.py
│   │   ├── playlist.py      # Pydantic schemas (Status, Track, Playlist)
│   │   └── operations.py    # CRUD operations (get/create/update)
│   ├── routes/
│   │   ├── __init__.py
│   │   └── playlist.py      # API endpoints
│   └── services/
│       ├── __init__.py
│       ├── youtube.py       # yt-dlp wrapper (extract + download)
│       ├── storage.py       # R2 upload/delete/URL generation
│       └── processor.py     # Background task (process_playlist)
├── static/
│   └── player/
│       └── player.html      # Monolithic player widget (HTML+CSS+JS)
└── tests/
    ├── conftest.py          # Fixtures, test DB setup
    ├── test_api.py          # API endpoint tests
    ├── test_database.py     # CRUD operation tests
    └── test_services.py     # Service layer tests
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check, returns `{"status":"ok"}` |
| POST | `/api/playlist` | Submit playlist URL, returns playlist + tracks |
| GET | `/api/playlist/{id}` | Get playlist status and track list |
| GET | `/api/track/{id}` | Redirect to R2 CDN URL for audio |

### Example: Submit Playlist
```bash
curl -X POST https://audio.imagehut.ch/api/playlist \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/playlist?list=PLxxxxxxx"}'
```

### Example: Check Status
```bash
curl https://audio.imagehut.ch/api/playlist/PLxxxxxxx
```

## Player Widget

Located at `static/player/player.html`. Monolithic file with HTML, CSS, JS.

### CSS Variables (for theming)
```css
.audio-player {
  --player-bg: #fff;       /* background */
  --player-text: #000;     /* text color */
  --player-border: #000;   /* borders */
  --player-accent: #000;   /* buttons, progress, active track */
  --player-muted: #666;    /* secondary text */
}
```

### JS Config (lines 81-82)
```javascript
var PLAYLIST_URL = "https://www.youtube.com/playlist?list=...";  // TODO: make dynamic
var API_BASE = "https://audio.imagehut.ch";
```

### Features
- Prev/Play/Next controls
- Progress bar with seek
- Track list with status indicators
- Auto-advances to next track
- Polls server while tracks processing
- Debug panel (toggle via button)

## Deployment

### Initial Deploy
```bash
# On VPS
mkdir -p /opt/youtube-cache/data
chmod 755 /opt/youtube-cache/data
git clone -b main https://github.com/null-works/jcink_audio.git /opt/youtube-cache/app
cd /opt/youtube-cache/app
docker build -t audio-cache .
```

Then in Portainer, create stack with:
```yaml
services:
  audio-cache:
    image: audio-cache
    container_name: audio-cache
    restart: unless-stopped
    ports:
      - "8942:8000"
    volumes:
      - /opt/youtube-cache/data:/app/data
    environment:
      - R2_ENDPOINT=https://5215ebbf6291827b415632f0cd0eae79.r2.cloudflarestorage.com
      - R2_BUCKET=imagehut-media
      - R2_ACCESS_KEY=b6cf7481eae8fddbd2abfd9762246606
      - R2_SECRET_KEY=5047f0a7f482f2347b442eefa06aad455cd5e5e7f70c6a730d5c163f95e34386
      - R2_PUBLIC_URL=https://media.imagehut.ch
      - MAX_TRACKS=10
      - AUDIO_BITRATE=128k
      - DATABASE_PATH=/app/data/cache.db
```

**Important**: Turn OFF "Re-pull image" toggle (it's a local image).

### Update Deploy
```bash
cd /opt/youtube-cache/app
git pull
docker build -t audio-cache .
# Then redeploy stack in Portainer
```

## Development

### Run Tests
```bash
python3 -m pytest -v
```

### Run Locally
```bash
export R2_ENDPOINT=https://5215ebbf6291827b415632f0cd0eae79.r2.cloudflarestorage.com
export R2_BUCKET=imagehut-media
export R2_ACCESS_KEY=b6cf7481eae8fddbd2abfd9762246606
export R2_SECRET_KEY=5047f0a7f482f2347b442eefa06aad455cd5e5e7f70c6a730d5c163f95e34386
export R2_PUBLIC_URL=https://media.imagehut.ch
export DATABASE_PATH=./data/cache.db

uvicorn app.main:app --reload --port 8000
```

### Debug Commands
```bash
# Check container logs
docker logs -f audio-cache

# List files in R2
docker exec audio-cache python3 -c "
from app.services.storage import get_r2_client
from app.config import settings
client = get_r2_client()
result = client.list_objects_v2(Bucket=settings.r2_bucket, Prefix='audio/')
for obj in result.get('Contents', []):
    print(obj['Key'])
"

# Test yt-dlp inside container
docker exec audio-cache yt-dlp --version
docker exec audio-cache yt-dlp --flat-playlist --dump-json "https://www.youtube.com/playlist?list=PLxxxxx"
```

## Key Implementation Details

### yt-dlp Output Parsing
yt-dlp `--flat-playlist --dump-json` outputs JSONL (one JSON object per line), not a single JSON with `entries` array. See `app/services/youtube.py:76-114`.

### Background Processing
Uses FastAPI's `BackgroundTasks` to process tracks after returning response. See `app/services/processor.py`.

### R2 URL Generation
Uses public R2 custom domain (`media.imagehut.ch`) instead of presigned URLs. See `app/services/storage.py:25-30`.

### Database
SQLite via aiosqlite. Tables: `playlists`, `tracks`. Auto-created on startup. See `app/database.py`.

## TODO (for Jcink integration)

- [ ] Remove Debug button from player for production
- [ ] Make PLAYLIST_URL dynamic (read from Jcink custom field)
- [ ] Style player to match forum theme
- [ ] Handle multiple players on same page (unique IDs)

## Contact

User is Kyle, IT support professional. Prefers:
- Direct, practical solutions
- Minimal fluff
- Working code over explanations
