"""Wire the library, starter pack, and optional HTTP source."""

from __future__ import annotations

from dataclasses import dataclass

from memeframe.config import Settings, get_settings
from memeframe.providers import CompatibleCaptioner, HashEmbedder, RuleCaptioner
from memeframe.sources import HttpJsonSource, LibrarySource, Registry, StarterPackSource
from memeframe.store import Store


@dataclass
class AppContext:
    settings: Settings
    store: Store
    registry: Registry
    embedder: HashEmbedder
    captioner: RuleCaptioner | CompatibleCaptioner


def build_context(settings: Settings | None = None) -> AppContext:
    settings = settings or get_settings()
    settings.home.mkdir(parents=True, exist_ok=True)
    store = Store(settings.db_path)
    # Embeddings stay local so search never hits the network, even with an API key.
    embedder = HashEmbedder()
    if settings.api_key:
        captioner: RuleCaptioner | CompatibleCaptioner = CompatibleCaptioner(settings, RuleCaptioner())
    else:
        captioner = RuleCaptioner()
    registry = Registry()
    registry.register(LibrarySource(store, embedder))
    registry.register(StarterPackSource())
    registry.register(HttpJsonSource(settings.http_source_url, settings.http_source_header))
    return AppContext(
        settings=settings,
        store=store,
        registry=registry,
        embedder=embedder,
        captioner=captioner,
    )
