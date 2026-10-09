"""Small bilingual web app over the same search path the MCP server uses."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from memeframe.bootstrap import AppContext, build_context
from memeframe.ingest import IngestError, ingest_bytes, split_tags
from memeframe.search import search_memes
from memeframe.sources import starter_by_id, svg_for

INDEX_PATH = Path(__file__).with_name("web") / "index.html"
_LIBRARY_NAME = re.compile(r"^[a-f0-9]{32}\.(png|jpg|gif|webp|svg)$")


def create_app(ctx: AppContext | None = None) -> FastAPI:
    app = FastAPI(title="memeframe", version="0.1.0")
    app.state.ctx = ctx or build_context()

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        if not INDEX_PATH.is_file():
            raise HTTPException(status_code=500, detail="web/index.html missing")
        return INDEX_PATH.read_text(encoding="utf-8")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/sources")
    def sources() -> dict:
        return {"sources": [source.info() for source in app.state.ctx.registry.list()]}

    @app.get("/api/search")
    def search(q: str = "", sources: str = "", page: int = 1, limit: int = 12) -> dict:
        ids = [item.strip() for item in sources.split(",") if item.strip()] or None
        result = search_memes(app.state.ctx, q, ids, page, limit)
        return result.to_dict()

    @app.post("/api/upload")
    async def upload(
        file: UploadFile = File(...),
        title: str = Form(""),
        title_en: str = Form(""),
        tags: str = Form(""),
    ) -> dict:
        data = await file.read()
        try:
            meme = ingest_bytes(
                app.state.ctx,
                data,
                file.filename or "upload",
                title,
                title_en,
                split_tags(tags),
            )
        except IngestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return meme.to_dict()

    @app.get("/media/starter/{file_name}")
    def starter_media(file_name: str) -> Response:
        if not file_name.endswith(".svg"):
            raise HTTPException(status_code=404)
        meme = starter_by_id(file_name[: -len(".svg")])
        if meme is None:
            raise HTTPException(status_code=404)
        return Response(content=svg_for(meme), media_type="image/svg+xml")

    @app.get("/media/library/{file_name}")
    def library_media(file_name: str) -> FileResponse:
        if not _LIBRARY_NAME.fullmatch(file_name):
            raise HTTPException(status_code=404)
        root = app.state.ctx.settings.library_dir.resolve()
        path = (root / file_name).resolve()
        if path.parent != root or not path.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(path)

    return app


def __getattr__(name: str) -> FastAPI:
    if name == "app":
        application = create_app()
        globals()["app"] = application
        return application
    raise AttributeError(name)
