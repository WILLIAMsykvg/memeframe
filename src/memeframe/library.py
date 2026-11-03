"""Local library list and delete helpers shared by API, CLI, and MCP."""

from __future__ import annotations

from pathlib import Path

from memeframe.bootstrap import AppContext
from memeframe.models import Meme


def list_library(ctx: AppContext) -> list[Meme]:
    return ctx.store.all_memes()


def delete_library_meme(ctx: AppContext, meme_id: str) -> Meme | None:
    meme = ctx.store.delete(meme_id)
    if meme is None:
        return None
    if library_file_exists(ctx, meme):
        (ctx.settings.library_dir / meme.filename).unlink(missing_ok=True)
    return meme


def library_file_exists(ctx: AppContext, meme: Meme) -> bool:
    if not meme.filename:
        return False
    return (Path(ctx.settings.library_dir) / meme.filename).is_file()
