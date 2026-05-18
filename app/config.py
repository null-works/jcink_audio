from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    r2_endpoint: str
    r2_bucket: str
    r2_access_key: str
    r2_secret_key: str
    r2_public_url: str = "https://media.imagehut.ch"
    max_tracks: int = 15
    audio_bitrate: str = "128k"
    database_path: str = "/app/data/cache.db"
    admin_ips: str = ""  # Comma-separated in env: ADMIN_IPS=1.2.3.4,5.6.7.8
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    # Dashboard auth — real values supplied via env (.env), never committed
    dashboard_password: str = ""  # DASHBOARD_PASSWORD
    dashboard_secret_key: str = ""  # DASHBOARD_SECRET_KEY
    # Path to a Netscape-format cookies.txt for yt-dlp. Required for YouTube
    # downloads from datacenter IPs (YouTube bot-check). Empty = no cookies.
    youtube_cookies_file: str = ""  # YOUTUBE_COOKIES_FILE
    # Base URL of a bgutil PO-token provider. YouTube now also requires a
    # PO token (beyond cookies) or it returns only storyboard images.
    # Empty = don't request PO tokens.
    youtube_pot_base_url: str = ""  # YOUTUBE_POT_BASE_URL
    # SOCKS/HTTP proxy for yt-dlp. The VPS IP is YouTube-blocked; route
    # through the yt-egress sidecar (egresses via inkwitch's clean IP).
    youtube_proxy: str = ""  # YOUTUBE_PROXY (e.g. socks5h://yt-egress:1080)

    class Config:
        env_prefix = ""


settings = Settings()
