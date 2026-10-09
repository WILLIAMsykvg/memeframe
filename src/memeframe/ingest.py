"""Save an upload, then caption and embed it once."""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from memeframe.bootstrap import AppContext
from memeframe.models import Meme
from memeframe.rank import meme_text

_TAGS = re.compile(r"[,，]")
_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}


class IngestError(ValueError):
    pass


def split_tags(raw: str) -> list[str]:
    return [part.strip() for part in _TAGS.split(raw) if part.strip()]


def detect_format(data: bytes, filename: str) -> str:
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"GIF8"):
        return "gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"
    head = data[:300].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head):
        return "svg"
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "jpeg":
        return "jpg"
    if ext in _MIME and head:
        return ext
    return ""


def ingest_bytes(ctx: AppContext, data: bytes, filename: str, title: str, title_en: str, tags: list[str]) -> Meme:
    settings = ctx.settings
    if len(data) > settings.max_upload_bytes:
        raise IngestError("file is too large")
    image_format = detect_format(data, filename)
    if not image_format:
        raise IngestError("unsupported image type")
    digest = hashlib.sha256(data).hexdigest()
    existing = ctx.store.get_by_sha(digest)
    if existing:
        return existing

    written = ctx.captioner.caption(data, Path(filename).name, title, tags, _MIME[image_format])
    stem = Path(filename).stem.replace("-", " ").replace("_", " ").strip()
    resolved_title = title.strip() or written.caption or stem or "untitled"
    resolved_title_en = title_en.strip() or written.caption_en
    meme_id = uuid.uuid4().hex
    stored_name = f"{meme_id}.{image_format}"
    settings.library_dir.mkdir(parents=True, exist_ok=True)
    (settings.library_dir / stored_name).write_bytes(data)
    meme = Meme(
        id=meme_id,
        title=resolved_title,
        title_en=resolved_title_en,
        caption=written.caption or resolved_title,
        caption_en=written.caption_en,
        tags=written.tags or tags,
        url=f"/media/library/{stored_name}",
        source_id="library",
        sha256=digest,
        format=image_format,
        filename=stored_name,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    ctx.store.insert(meme, ctx.embedder.embed_text(meme_text(meme)))
    return meme


def reindex(ctx: AppContext) -> int:
    memes = ctx.store.all_memes()
    for meme in memes:
        ctx.store.save_embedding(meme.id, ctx.embedder.embed_text(meme_text(meme)))
    return len(memes)
