from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    r2_endpoint: str
    r2_bucket: str
    r2_access_key: str
    r2_secret_key: str
    max_tracks: int = 10
    audio_bitrate: str = "128k"
    database_path: str = "/app/data/cache.db"

    class Config:
        env_prefix = ""


settings = Settings()
