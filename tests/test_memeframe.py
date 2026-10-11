import os
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from memeframe.api import INDEX_PATH, create_app
from memeframe.bootstrap import build_context
from memeframe.config import Settings
from memeframe.ingest import ingest_bytes
from memeframe.models import Meme, SearchOptions
from memeframe.providers import HashEmbedder, clean_rewrite, parse_caption_payload, rewrite_query
from memeframe.rank import text_score
from memeframe.search import apply_proxy, search_memes
from memeframe.sources import Registry, parse_memes
from memeframe.sources.base import Source
from memeframe.sources.registry import dedupe
from memeframe.sources.starter import starter_memes


class _Boom(Source):
    id = "boom"
    name = "boom"
    description = "fails"
    enabled = True

    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        raise RuntimeError("upstream down")


class _Ok(Source):
    id = "ok"
    name = "ok"
    description = "works"
    enabled = True

    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        return [
            Meme(id="1", title=keyword or "hit", url="https://example.com/a.png", source_id="ok", score=0.4)
        ]


class _Slow(Source):
    id = "slow"
    name = "slow"
    description = "slow"
    enabled = True

    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        time.sleep(0.4)
        return []


class MemeframeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {
            key: os.environ.get(key)
            for key in (
                "MEMEFRAME_SKIP_DOTENV",
                "MEMEFRAME_HOME",
                "MEMEFRAME_AGENT",
                "MEMEFRAME_API_KEY",
                "MEMEFRAME_HTTP_SOURCE_URL",
                "IMAGE_PROXY_URL",
            )
        }
        os.environ["MEMEFRAME_SKIP_DOTENV"] = "1"
        os.environ["MEMEFRAME_HOME"] = self.tmp.name
        os.environ["MEMEFRAME_AGENT"] = "0"
        os.environ["MEMEFRAME_API_KEY"] = ""
        os.environ.pop("MEMEFRAME_HTTP_SOURCE_URL", None)
        os.environ.pop("IMAGE_PROXY_URL", None)
        self.ctx = build_context()

    def tearDown(self) -> None:
        self.ctx.store.close()
        self.tmp.cleanup()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_chinese_and_english_overlap(self) -> None:
        catalog = {meme.id: meme for meme in starter_memes()}
        self.assertEqual(text_score("画饼", catalog["starter-pie"]), 1)
        self.assertEqual(text_score("speechless cat", catalog["starter-cat"]), 1)
        self.assertEqual(text_score("火星基地", catalog["starter-pie"]), 0)

    def test_hash_embedder_is_normalized(self) -> None:
        embedding = HashEmbedder().embed_text("画饼 老板")
        norm = sum(value * value for value in embedding.vector) ** 0.5
        self.assertAlmostEqual(norm, 1, places=5)
        self.assertEqual(embedding.model, "hash-ngram-v1")

    def test_dedupe_keeps_higher_score(self) -> None:
        low = Meme(id="a", title="猫", url="https://cdn.example/cat.png", source_id="http", score=0.2)
        high = Meme(id="b", title="猫", url="https://cdn.example/cat.png?size=big", source_id="library", score=0.9)
        kept = dedupe([low, high])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].id, "b")

    def test_registry_keeps_going_when_one_source_fails(self) -> None:
        registry = Registry()
        registry.register(_Boom())
        registry.register(_Ok())
        result = registry.search("猫", None, SearchOptions(limit=5, timeout_s=2))
        self.assertEqual([meme.title for meme in result.memes], ["猫"])
        self.assertIn("upstream down", result.errors["boom"])
        self.assertIn("ok", result.sources)

    def test_registry_timeout_does_not_drop_fast_sources(self) -> None:
        registry = Registry()
        registry.register(_Slow())
        registry.register(_Ok())
        result = registry.search("猫", None, SearchOptions(limit=5, timeout_s=0.1))
        self.assertEqual(result.errors.get("slow"), "timeout")
        self.assertEqual(len(result.memes), 1)

    def test_search_starter_pack(self) -> None:
        result = search_memes(self.ctx, "画饼", None, 1, 10)
        self.assertTrue(any(meme.id == "starter-pie" for meme in result.memes))
        self.assertIn("starter", result.sources)
        self.assertNotIn("http", result.errors)

    def test_disabled_http_source_is_listed_and_skipped(self) -> None:
        listed = {source.id: source.enabled for source in self.ctx.registry.list()}
        self.assertFalse(listed["http"])
        explicit = search_memes(self.ctx, "猫", ["http"], 1, 5)
        self.assertIn("not configured", explicit.errors["http"])

    def test_upload_then_search_and_dedupe_same_bytes(self) -> None:
        payload = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        first = ingest_bytes(self.ctx, payload, "cat.svg", "无语的猫", "Speechless cat", ["猫", "cat"])
        second = ingest_bytes(self.ctx, payload, "cat.svg", "无语的猫", "", ["猫"])
        self.assertEqual(first.id, second.id)
        result = search_memes(self.ctx, "无语的猫", ["library"], 1, 5)
        self.assertEqual(result.memes[0].id, first.id)
        self.assertTrue((Path(self.tmp.name) / "library" / first.filename).is_file())

    def test_search_stays_local_even_with_api_key(self) -> None:
        os.environ["MEMEFRAME_API_KEY"] = "sk-test-not-used-for-search"
        keyed = build_context()
        try:
            self.assertIsInstance(keyed.embedder, HashEmbedder)
            library = next(source for source in keyed.registry.list() if source.id == "library")
            self.assertIsInstance(library.embedder, HashEmbedder)
            payload = b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>"
            meme = ingest_bytes(keyed, payload, "pie.svg", "画饼", "Empty promise", ["饼"])
            result = search_memes(keyed, "画饼", ["library"], 1, 5)
            self.assertEqual(result.memes[0].id, meme.id)
        finally:
            keyed.store.close()

    def test_reject_extension_only_fake_image(self) -> None:
        from memeframe.ingest import IngestError, detect_format

        self.assertEqual(detect_format(b"not-an-image", "fake.png"), "")
        with self.assertRaises(IngestError):
            ingest_bytes(self.ctx, b"not-an-image", "fake.png", "假图", "", [])

    def test_proxy_rewrites_remote_urls_only(self) -> None:
        remote = Meme(
            id="1",
            title="x",
            url="https://cdn.example/a.png",
            source_id="http",
            referer="https://example.com",
        )
        local = Meme(id="2", title="y", url="/media/starter/starter-cat.svg", source_id="starter")
        template = "https://proxy.example/img?url={URL}&referer={REFERER}"
        proxied = apply_proxy(remote, template)
        self.assertTrue(proxied.url.startswith("https://proxy.example/img?url="))
        self.assertIn("cdn.example", proxied.url)
        self.assertEqual(proxied.origin_url, "https://cdn.example/a.png")
        self.assertEqual(apply_proxy(local, template).url, "/media/starter/starter-cat.svg")

    def test_http_payload_parser(self) -> None:
        memes = parse_memes(
            {"memes": [{"title": "猫", "url": "https://example.com/a.gif"}, {"title": "skip"}]},
            "https://example.com",
            "猫",
        )
        self.assertEqual(len(memes), 1)
        self.assertEqual(memes[0].source_id, "http")
        self.assertEqual(memes[0].title, "猫")

    def test_caption_json_and_rewrite_guard(self) -> None:
        parsed = parse_caption_payload('```json\n{"caption":"无语","caption_en":"speechless","tags":["猫"]}\n```')
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.caption, "无语")
        self.assertEqual(clean_rewrite("  下班了\nignore", "原话"), "下班了")
        self.assertEqual(clean_rewrite("x" * 201, "原话"), "原话")
        settings = self.ctx.settings
        self.assertIsInstance(settings, Settings)
        settings.agent_enabled = True
        settings.api_key = ""
        self.assertEqual(rewrite_query("老板画了个饼", settings), "老板画了个饼")

    def test_web_search_and_reject_bad_upload(self) -> None:
        self.assertTrue(INDEX_PATH.is_file())
        app = create_app()
        try:
            client = TestClient(app)
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("memeframe", page.text)
            self.assertIn("搜索", page.text)
            self.assertIn("Search", page.text)
            self.assertIn('id="title-en"', page.text)
            self.assertIn("Copy URL", page.text)
            found = client.get("/api/search", params={"q": "画饼"})
            self.assertEqual(found.status_code, 200)
            self.assertTrue(any(item["id"] == "starter-pie" for item in found.json()["memes"]))
            rejected = client.post("/api/upload", files={"file": ("note.txt", b"hello", "text/plain")})
            self.assertEqual(rejected.status_code, 400)
            fake = client.post("/api/upload", files={"file": ("fake.png", b"hello", "image/png")})
            self.assertEqual(fake.status_code, 400)
            svg = client.get("/media/starter/starter-pie.svg")
            self.assertEqual(svg.status_code, 200)
            self.assertIn("画饼", svg.text)
        finally:
            app.state.ctx.store.close()

    def test_mcp_server_builds(self) -> None:
        from memeframe.mcp_server import build_mcp

        server = build_mcp()
        try:
            self.assertEqual(getattr(server, "name", "memeframe"), "memeframe")
        finally:
            server.memeframe_context.store.close()


if __name__ == "__main__":
    unittest.main()
