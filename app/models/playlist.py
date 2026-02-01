from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class Status(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


class TrackBase(BaseModel):
    id: str
    playlist_id: str
    title: str | None = None
    duration: int | None = None
    r2_key: str | None = None
    r2_url: str | None = None
    status: Status = Status.PENDING
    position: int


class Track(TrackBase):
    created_at: datetime | None = None


class PlaylistBase(BaseModel):
    id: str
    url: str
    status: Status = Status.PENDING
    track_count: int = 0


class Playlist(PlaylistBase):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlaylistResponse(BaseModel):
    id: str
    url: str
    status: Status
    track_count: int
    tracks: list[Track] = []


class PlaylistSubmit(BaseModel):
    url: str
