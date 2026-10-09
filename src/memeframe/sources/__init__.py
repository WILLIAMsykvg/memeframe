"""Source adapters."""

from memeframe.sources.base import Source
from memeframe.sources.http_json import HttpJsonSource, parse_memes
from memeframe.sources.library import LibrarySource
from memeframe.sources.registry import Registry, dedupe
from memeframe.sources.starter import StarterPackSource, starter_by_id, svg_for

__all__ = [
    "HttpJsonSource",
    "LibrarySource",
    "Registry",
    "Source",
    "StarterPackSource",
    "dedupe",
    "parse_memes",
    "starter_by_id",
    "svg_for",
]
