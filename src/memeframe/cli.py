"""Command line. Web, MCP, search, and upload share one library."""

from __future__ import annotations

import argparse
import json
import sys

from memeframe.bootstrap import build_context
from memeframe.ingest import ingest_bytes, reindex, split_tags
from memeframe.search import search_memes


def main(argv: list[str] | None = None) -> None:
    _configure_stdio()
    parser = argparse.ArgumentParser(
        prog="memeframe",
        description="Meme search framework / 梗图搜索框架",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search memes / 搜索梗图")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--sources", default="", help="Comma-separated source ids / 逗号分隔的源 ID")
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--limit", type=int, default=10)

    upload = sub.add_parser("upload", help="Index one image / 入库一张图")
    upload.add_argument("path")
    upload.add_argument("--title", default="")
    upload.add_argument("--title-en", default="")
    upload.add_argument("--tags", default="")

    sub.add_parser("sources", help="List sources / 列出数据源")
    sub.add_parser("reindex", help="Rebuild embeddings from stored text / 按已有文字重建向量")

    serve = sub.add_parser("serve", help="Run the web app / 启动网页")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    sub.add_parser("mcp", help="Run the MCP server on stdio / 以 stdio 启动 MCP")

    args = parser.parse_args(argv)
    if args.command == "mcp":
        from memeframe.mcp_server import main as mcp_main

        mcp_main()
        return
    if args.command == "serve":
        import uvicorn

        from memeframe.api import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)
        return

    ctx = build_context()
    if args.command == "sources":
        print(json.dumps([source.info() for source in ctx.registry.list()], ensure_ascii=False, indent=2))
        return
    if args.command == "reindex":
        print(reindex(ctx))
        return
    if args.command == "upload":
        from pathlib import Path

        file_path = Path(args.path)
        if not file_path.is_file():
            print("file not found / 找不到文件", file=sys.stderr)
            sys.exit(1)
        meme = ingest_bytes(
            ctx,
            file_path.read_bytes(),
            file_path.name,
            args.title,
            args.title_en,
            split_tags(args.tags),
        )
        print(json.dumps(meme.to_dict(), ensure_ascii=False, indent=2))
        return

    ids = [item.strip() for item in args.sources.split(",") if item.strip()] or None
    result = search_memes(ctx, args.query, ids, args.page, args.limit)
    if result.rewritten_query:
        print(f"rewritten / 改写: {result.rewritten_query}")
    for meme in result.memes:
        title = meme.title_en if meme.title_en else meme.title
        print(f"{meme.score:.2f}  [{meme.source_id}] {meme.title} / {title}  {meme.url}")
    if result.errors:
        print(json.dumps(result.errors, ensure_ascii=False), file=sys.stderr)


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
