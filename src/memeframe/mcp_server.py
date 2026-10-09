"""MCP tools for Cursor, Claude, and other clients.

stdout is reserved for the protocol. Logs stay off this stream.
stdout 只留给 MCP 协议。
"""

from __future__ import annotations

import json

from memeframe.bootstrap import build_context
from memeframe.ingest import IngestError, ingest_bytes, split_tags
from memeframe.search import search_memes


def build_mcp():
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError:
        from mcp.server.fastmcp import FastMCP as MCPServer

    mcp = MCPServer("memeframe")
    ctx = build_context()
    mcp.memeframe_context = ctx

    @mcp.tool()
    def search_meme(keyword: str, sources: str = "", page: int = 1, limit: int = 10) -> str:
        """Search memes across enabled sources. 跨已启用的数据源搜索梗图。

        keyword: a scene or caption, for example 画饼 or speechless cat.
        sources: optional comma-separated ids such as library,starter,http.
        Vision models are not called for this search.
        """
        ids = [item.strip() for item in sources.split(",") if item.strip()] or None
        result = search_memes(ctx, keyword, ids, page, limit)
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    @mcp.tool()
    def list_sources() -> str:
        """List meme sources and which ones are enabled. 列出梗图数据源，以及是否已启用。"""
        payload = [source.info() for source in ctx.registry.list()]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @mcp.tool()
    def upload_meme(path: str, title: str = "", title_en: str = "", tags: str = "") -> str:
        """Index a local image. Caption and embedding run once here. 把本地图片入库。描述和向量只在这一步生成。"""
        from pathlib import Path

        file_path = Path(path)
        if not file_path.is_file():
            return json.dumps({"error": "file not found"}, ensure_ascii=False)
        try:
            meme = ingest_bytes(ctx, file_path.read_bytes(), file_path.name, title, title_en, split_tags(tags))
        except IngestError as exc:
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        return json.dumps(meme.to_dict(), ensure_ascii=False, indent=2)

    return mcp


def main() -> None:
    build_mcp().run()


if __name__ == "__main__":
    main()
