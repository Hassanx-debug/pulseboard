from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class TrendSnapshotIn(BaseModel):
    source_id: int
    external_id: str
    title: str
    url: Optional[str] = None
    author: Optional[str] = None
    score: int = 0
    comment_count: int = 0
    heat_score: float = 0.0
    posted_at: Optional[datetime] = None
    raw_payload: Optional[dict] = None
    tags: list[str] = Field(default_factory=list)

class TrendSnapshotOut(BaseModel):
    id: str
    title: str
    url: Optional[str]
    author: Optional[str]
    score: int
    comment_count: int
    heat_score: float
    posted_at: Optional[datetime]
    fetched_at: datetime
    tags: list[str]
    source: str
    source_name: str

class TopUrlEntry(BaseModel):
    title: str
    url: Optional[str]
    source: str
    heat: float

class TrendingTopicOut(BaseModel):
    id: str
    topic: str
    mention_count: int
    avg_heat: float
    peak_heat: float
    momentum: float
    source_breakdown: dict[str, int]
    top_urls: list[TopUrlEntry]
    window_start: datetime
    window_end: datetime
    computed_at: datetime

class IngestResult(BaseModel):
    reddit_fetched: int = 0
    hn_fetched: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0
    errors: list[str] = Field(default_factory=list)