"""Uploaded memes. Ranking uses the embedding written at ingest."""

from __future__ import annotations

from memeframe.models import Meme, SearchOptions
from memeframe.sources.base import Source
from memeframe.store import Store


class LibrarySource(Source):
    id = "library"
    name = "本地图库 · Local library"
    description = "上传时写入描述和本地向量。Search uses stored text; no network call."
    requires_auth = False
    enabled = True

    def __init__(self, store: Store, embedder: object) -> None:
        self.store = store
        self.embedder = embedder

    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        embedding = self.embedder.embed_text(keyword) if keyword.strip() else None
        hash_model = embedding.model.startswith("hash") if embedding else False
        return self.store.search(keyword, embedding, options.limit, hash_model)
