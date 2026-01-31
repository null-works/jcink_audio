# YouTube Audio Cache for Jcink Roleplay Forum

## Project Overview

Self-hosted YouTube playlist to MP3 converter for a Jcink roleplay forum. Server-side extraction via yt-dlp → Cloudflare R2 storage → custom HTML5 player widget that forum users embed in their posts.

## Infrastructure (COMPLETE)

All infrastructure is set up and tested:

| Component | Status | Details |
|-----------|--------|---------|
| VPS | ✅ | Ubuntu + Portainer at `sys.inklit.ch` |
| Domain | ✅ | `audio.imagehut.ch` → nginx → port 8942 |
| SSL | ✅ | Certbot/Let's Encrypt |
| R2 Bucket | ✅ | `imagehut-media` on Cloudflare |
| Nginx | ✅ | Reverse proxy configured, tested working |

## R2 Credentials

```
Endpoint: https://5215ebbf6291827b415632f0cd0eae79.r2.cloudflarestorage.com
Bucket: imagehut-media
Access Key: b6cf7481eae8fddbd2abfd9762246606
Secret Key: 5047f0a7f482f2347b442eefa06aad455cd5e5e7f70c6a730d5c163f95e34386
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Jcink Forum    │────▶│  audio.imagehut.ch │────▶│  R2 Bucket  │
│  (embed widget) │     │  (API + Player)    │     │  (MP3 files)│
└─────────────────┘     └──────────────────┘     └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │   yt-dlp     │
                        │  (extract)   │
                        └──────────────┘
```

## Constraints

- **Max 10 songs per playlist** (server-enforced)
- **128kbps MP3** (~3.5MB per song, ~1MB/min)
- **~35MB per character** (10 songs × 3.5MB)
- **Target: 120-200 characters** = 4-7GB total
- **R2 free tier**: 10GB storage, zero egress

## Container Requirements

- **Port**: 8942 (nginx already proxies to this)
- **Volume**: `/opt/youtube-cache/data` (for SQLite + temp files)
- **Deploy via**: Portainer at `https://sys.inklit.ch:9443`

## What Needs to Be Built

### 1. Backend API (Python/Node)

Endpoints:
- `POST /api/playlist` - Submit YouTube playlist URL, returns job ID
- `GET /api/playlist/{id}` - Get playlist status/tracks
- `GET /api/track/{id}` - Stream/redirect to R2 URL

Flow:
1. User submits playlist URL
2. Backend validates (max 10 tracks)
3. yt-dlp extracts audio → converts to 128kbps MP3
4. Upload to R2 at `audio/{playlist_id}/{track_id}.mp3`
5. Store metadata in SQLite
6. Return R2 URLs to client

### 2. Embeddable Player Widget

- HTML5 audio player
- Works inside Jcink forum posts (iframe or direct embed)
- Playlist support (next/prev track)
- Minimal, clean UI
- Mobile-friendly

### 3. Simple Admin/Submit UI

- Paste playlist URL
- See processing status
- Get embed code when done

## Tech Suggestions

- **Backend**: Python (FastAPI) or Node (Express)
- **yt-dlp**: Install in container, call via subprocess
- **R2**: Use boto3 (Python) or @aws-sdk/client-s3 (Node) with S3-compatible config
- **Database**: SQLite (single file at `/opt/youtube-cache/data/cache.db`)
- **Container**: Single Dockerfile, deploy as Portainer stack

## File Structure Suggestion

```
youtube-audio-cache/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt (or package.json)
├── app/
│   ├── main.py (or index.js)
│   ├── routes/
│   ├── services/
│   │   ├── youtube.py    # yt-dlp wrapper
│   │   └── storage.py    # R2 upload/URL generation
│   └── models/
├── static/
│   └── player/           # Embeddable widget files
└── templates/
    └── submit.html       # Simple submission UI
```

## Portainer Stack Config

When ready, deploy in Portainer as a new stack. Example compose:

```yaml
services:
  audio-cache:
    build: .
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
      - MAX_TRACKS=10
      - AUDIO_BITRATE=128k
```

## Testing

Once deployed, verify:
1. `curl https://audio.imagehut.ch/health` returns 200
2. Submit a small playlist (2-3 tracks)
3. Confirm MP3s appear in R2 bucket under `audio/` prefix
4. Test embed player in a Jcink test post

## Previous Context

This project was set up in a conversation that covered:
- Evaluating Caddy vs nginx (chose existing nginx)
- Setting up R2 bucket and credentials
- Upgrading Chevereto to Pro (separate service on same VPS)
- Testing the full nginx → container pipe

The infrastructure is solid. Now just need the application code.

## Development Workflow

**IMPORTANT: Follow this workflow for every feature/change.**

### 1. Design First

Before writing code, provide a diagram or explanation showing:
- What the feature does
- How data flows through the system
- Which files/components are affected

Example:
```
Profile loads → JS reads custom field → POST /api/playlist → yt-dlp → R2 → return URLs
```

### 2. Unit Tests

Run tests before and after changes:

```bash
# Run all tests
python3 -m pytest -v

# Run specific test file
python3 -m pytest tests/test_database.py -v

# Run with coverage (if installed)
python3 -m pytest --cov=app tests/
```

**Test requirements:**
- All new features must have corresponding tests
- Tests must pass before committing
- Database operations → `tests/test_database.py`
- API endpoints → `tests/test_api.py`
- Services → `tests/test_services.py` (create as needed)

### 3. Local Verification

Test the app locally before deploying:

```bash
# Set environment variables
export DATABASE_PATH=./data/cache.db
export R2_ENDPOINT=https://5215ebbf6291827b415632f0cd0eae79.r2.cloudflarestorage.com
export R2_BUCKET=imagehut-media
export R2_ACCESS_KEY=b6cf7481eae8fddbd2abfd9762246606
export R2_SECRET_KEY=5047f0a7f482f2347b442eefa06aad455cd5e5e7f70c6a730d5c163f95e34386
export MAX_TRACKS=10
export AUDIO_BITRATE=128k

# Run the app
uvicorn app.main:app --reload --port 8000

# Test health
curl http://localhost:8000/health
```

### 4. Commit Workflow

1. Design explanation/diagram
2. Write tests (TDD preferred)
3. Implement feature
4. Run tests: `python3 -m pytest -v`
5. Verify locally
6. Commit and push

## Contact

User is Kyle, IT support professional. Prefers:
- Direct, practical solutions
- Minimal fluff
- Working code over explanations
