"""Shared records for sources, storage, and search."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Meme:
    id: str
    title: str
    url: str
    source_id: str
    title_en: str = ""
    caption: str = ""
    caption_en: str = ""
    tags: list[str] = field(default_factory=list)
    sha256: str = ""
    format: str = ""
    filename: str = ""
    referer: str = ""
    origin_url: str = ""
    score: float = 0.0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.origin_url:
            self.origin_url = self.url

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "title_en": self.title_en,
            "caption": self.caption,
            "caption_en": self.caption_en,
            "tags": list(self.tags),
            "url": self.url,
            "origin_url": self.origin_url,
            "source_id": self.source_id,
            "format": self.format,
            "score": round(self.score, 4),
            "created_at": self.created_at,
        }


@dataclass
class SearchOptions:
    page: int = 1
    limit: int = 20
    timeout_s: float = 8.0


@dataclass
class Embedding:
    vector: list[float]
    model: str


@dataclass
class SearchResult:
    memes: list[Meme]
    sources: list[str]
    errors: dict[str, str]
    total: int
    duration_ms: int
    query: str = ""
    rewritten_query: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "rewritten_query": self.rewritten_query,
            "memes": [meme.to_dict() for meme in self.memes],
            "sources": self.sources,
            "errors": self.errors,
            "total": self.total,
            "duration_ms": self.duration_ms,
        }
