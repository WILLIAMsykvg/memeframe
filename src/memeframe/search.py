"""Merge source hits, then optionally rewrite the query before that merge."""

from __future__ import annotations

import time
from urllib.parse import quote

from memeframe.bootstrap import AppContext
from memeframe.models import Meme, SearchOptions, SearchResult
from memeframe.providers import rewrite_query


def search_memes(
    ctx: AppContext,
    query: str,
    source_ids: list[str] | None,
    page: int,
    limit: int,
) -> SearchResult:
    page = max(1, page)
    limit = min(max(1, limit), 50)
    started = time.perf_counter()
    settings = ctx.settings
    used = rewrite_query(query, settings)
    rewritten = used if used != query else ""
    fetch = SearchOptions(page=1, limit=page * limit, timeout_s=settings.source_timeout_s)
    result = ctx.registry.search(used, source_ids, fetch)
    result.memes = [apply_proxy(meme, settings.image_proxy_url) for meme in result.memes]
    total = len(result.memes)
    start = (page - 1) * limit
    result.memes = result.memes[start : start + limit]
    result.total = total
    result.query = query
    result.rewritten_query = rewritten
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    return result


def apply_proxy(meme: Meme, template: str) -> Meme:
    if not template or ("{URL}" not in template and "{SOURCE_URL}" not in template):
        return meme
    if not meme.url.startswith(("http://", "https://")):
        return meme
    encoded = quote(meme.url, safe="")
    referer = quote(meme.referer, safe="")
    meme.url = (
        template.replace("{URL}", encoded)
        .replace("{SOURCE_URL}", encoded)
        .replace("{REFERER}", referer)
    )
    return meme
