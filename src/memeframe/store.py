"""SQLite library. One caption embedding per meme, brute-force scan."""

from __future__ import annotations

import json
import sqlite3
import struct
import threading
from pathlib import Path

from memeframe.models import Embedding, Meme
from memeframe.rank import combine, cosine, text_score

SCHEMA = """
CREATE TABLE IF NOT EXISTS memes (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  title_en TEXT NOT NULL DEFAULT '',
  caption TEXT NOT NULL DEFAULT '',
  caption_en TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '[]',
  url TEXT NOT NULL,
  source_id TEXT NOT NULL,
  sha256 TEXT NOT NULL DEFAULT '',
  format TEXT NOT NULL DEFAULT '',
  filename TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_memes_sha ON memes(sha256);
CREATE TABLE IF NOT EXISTS embeddings (
  meme_id TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  dim INTEGER NOT NULL,
  vector BLOB NOT NULL
);
"""


def _pack(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack(blob: bytes, dim: int) -> list[float]:
    return list(struct.unpack(f"<{dim}f", blob))


class Store:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def insert(self, meme: Meme, embedding: Embedding) -> None:
        tags = json.dumps(meme.tags, ensure_ascii=False)
        with self._lock:
            try:
                self.conn.execute("BEGIN")
                self.conn.execute(
                    """
                    INSERT INTO memes (
                      id, title, title_en, caption, caption_en, tags, url,
                      source_id, sha256, format, filename, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        meme.id,
                        meme.title,
                        meme.title_en,
                        meme.caption,
                        meme.caption_en,
                        tags,
                        meme.url,
                        meme.source_id,
                        meme.sha256,
                        meme.format,
                        meme.filename,
                        meme.created_at,
                    ),
                )
                self._write_embedding(meme.id, embedding)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def save_embedding(self, meme_id: str, embedding: Embedding) -> None:
        with self._lock:
            self._write_embedding(meme_id, embedding)
            self.conn.commit()

    def _write_embedding(self, meme_id: str, embedding: Embedding) -> None:
        self.conn.execute(
            """
            INSERT INTO embeddings (meme_id, model, dim, vector)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(meme_id) DO UPDATE SET
              model = excluded.model,
              dim = excluded.dim,
              vector = excluded.vector
            """,
            (meme_id, embedding.model, len(embedding.vector), _pack(embedding.vector)),
        )

    def get_by_sha(self, digest: str) -> Meme | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM memes WHERE sha256 = ?", (digest,)).fetchone()
        return _row_to_meme(row) if row else None

    def all_memes(self) -> list[Meme]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM memes").fetchall()
        return [_row_to_meme(row) for row in rows]

    def search(self, query: str, embedding: Embedding | None, limit: int, hash_model: bool) -> list[Meme]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM memes").fetchall()
            vectors = {
                item["meme_id"]: item
                for item in self.conn.execute("SELECT meme_id, model, dim, vector FROM embeddings")
            }
        scored: list[Meme] = []
        blank = not query.strip()
        for row in rows:
            meme = _row_to_meme(row)
            keyword = 0.0 if blank else text_score(query, meme)
            vector = 0.0
            stored = vectors.get(meme.id)
            if (
                embedding
                and stored
                and stored["model"] == embedding.model
                and not (hash_model and keyword <= 0)
            ):
                vector = cosine(embedding.vector, _unpack(stored["vector"], stored["dim"]))
            if blank:
                meme.score = 0.2
            else:
                meme.score = combine(keyword, vector)
                if meme.score <= 0:
                    continue
            scored.append(meme)
        if blank:
            scored.sort(key=lambda meme: meme.created_at, reverse=True)
        else:
            scored.sort(key=lambda meme: (meme.score, meme.created_at), reverse=True)
        return scored[:limit]


def _row_to_meme(row: sqlite3.Row) -> Meme:
    try:
        tags = json.loads(row["tags"])
    except json.JSONDecodeError:
        tags = []
    if not isinstance(tags, list):
        tags = []
    return Meme(
        id=row["id"],
        title=row["title"],
        title_en=row["title_en"],
        caption=row["caption"],
        caption_en=row["caption_en"],
        tags=[str(tag) for tag in tags],
        url=row["url"],
        origin_url=row["url"],
        source_id=row["source_id"],
        sha256=row["sha256"],
        format=row["format"],
        filename=row["filename"],
        created_at=row["created_at"],
    )
