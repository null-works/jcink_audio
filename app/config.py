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

    class Config:
        env_prefix = ""


settings = Settings()
