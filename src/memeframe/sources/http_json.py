"""Remote keyword source with a small JSON contract.

Disabled until MEMEFRAME_HTTP_SOURCE_URL is set, same idea as o98k-ok/meme
skipping sources that lack a cookie or proxy.
未配置地址时关闭，和 o98k-ok/meme 跳过未配置源是同一思路。
"""

from __future__ import annotations

import httpx

from memeframe.models import Meme, SearchOptions
from memeframe.rank import text_score
from memeframe.sources.base import Source


class HttpJsonSource(Source):
    id = "http"
    name = "远程 JSON · HTTP JSON"
    description = "GET ?q=&page=&limit= ，返回 {\"memes\":[{\"title\",\"url\"}]} 。"
    requires_auth = False

    def __init__(self, url: str, header: str = "") -> None:
        self.url = url
        self.header_value = header
        self.enabled = bool(url)
        self.referer = url

    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        if not self.enabled:
            raise RuntimeError("source is not configured")
        response = httpx.get(
            self.url,
            params={"q": keyword, "page": options.page, "limit": options.limit},
            headers=_parse_header(self.header_value),
            timeout=options.timeout_s,
        )
        response.raise_for_status()
        return parse_memes(response.json(), self.referer, keyword)


def parse_memes(payload: object, referer: str, keyword: str = "") -> list[Meme]:
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    items = payload.get("memes") or payload.get("data") or []
    if not isinstance(items, list):
        raise ValueError("memes must be a list")
    memes: list[Meme] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("image") or "").strip()
        if not url:
            continue
        title = str(item.get("title") or item.get("name") or "meme").strip()
        title_en = str(item.get("title_en") or "").strip()
        caption = str(item.get("caption") or "").strip()
        caption_en = str(item.get("caption_en") or "").strip()
        tags = item.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        meme = Meme(
            id=str(item.get("id") or f"http-{index}"),
            title=title,
            title_en=title_en,
            caption=caption,
            caption_en=caption_en,
            tags=[str(tag) for tag in tags] if isinstance(tags, list) else [],
            url=url,
            source_id="http",
            format=str(item.get("format") or ""),
            referer=referer,
            score=0.45,
        )
        if keyword.strip():
            overlap = text_score(keyword, meme)
            meme.score = max(meme.score, overlap)
        memes.append(meme)
    return memes


def _parse_header(raw: str) -> dict[str, str]:
    if not raw or ":" not in raw:
        return {}
    name, value = raw.split(":", 1)
    name = name.strip()
    if not name:
        return {}
    return {name: value.strip()}
