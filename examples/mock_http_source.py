"""Tiny demo JSON source for the built-in `http` adapter.

Run:
  python examples/mock_http_source.py

Then in another shell:
  $env:MEMEFRAME_HTTP_SOURCE_URL = "http://127.0.0.1:8765/search"
  memeframe search 猫 --sources http
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CATALOG = [
    {
        "title": "无语的猫",
        "title_en": "Speechless cat",
        "url": "https://placehold.co/320x240/png?text=cat",
        "format": "png",
        "tags": ["猫", "cat"],
    },
    {
        "title": "画饼会议",
        "title_en": "Empty promise meeting",
        "url": "https://placehold.co/320x240/png?text=pie",
        "format": "png",
        "tags": ["画饼", "boss"],
    },
    {
        "title": "周五了",
        "title_en": "Friday mood",
        "url": "https://placehold.co/320x240/png?text=friday",
        "format": "png",
        "tags": ["周五", "friday"],
    },
]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self.send_error(404)
            return
        params = parse_qs(parsed.query)
        query = (params.get("q") or [""])[0].strip().lower()
        try:
            limit = int((params.get("limit") or ["10"])[0])
        except ValueError:
            limit = 10
        memes = []
        for item in CATALOG:
            blob = " ".join([item["title"], item["title_en"], " ".join(item["tags"])]).lower()
            if not query or query in blob:
                memes.append(item)
        body = ('{"memes": ' + _json_list(memes[: max(1, min(limit, 50))]) + "}").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print(f"[mock-http] {args[0]}")


def _json_list(items: list[dict]) -> str:
    import json

    return json.dumps(items, ensure_ascii=False)


def main() -> None:
    host, port = "127.0.0.1", 8765
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"mock http source on http://{host}:{port}/search")
    print('set MEMEFRAME_HTTP_SOURCE_URL=http://127.0.0.1:8765/search')
    server.serve_forever()


if __name__ == "__main__":
    main()
