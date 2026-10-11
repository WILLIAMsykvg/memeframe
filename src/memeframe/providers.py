"""Caption and embedding providers.

Search never calls these. Upload and reindex do.
搜索时不调用这里。上传和重建索引时才调用。
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from memeframe.config import Settings
from memeframe.models import Embedding
from memeframe.rank import l2_normalize, tokens

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


@dataclass
class CaptionResult:
    caption: str
    caption_en: str = ""
    tags: list[str] = field(default_factory=list)


class HashEmbedder:
    """Offline stand-in. Same text space for documents and queries."""

    model_name = "hash-ngram-v1"
    dim = 256

    def embed_text(self, text: str) -> Embedding:
        vector = [0.0] * self.dim
        pieces = list(tokens(text)) or ["empty"]
        for piece in pieces:
            digest = hashlib.sha256(piece.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        return Embedding(vector=l2_normalize(vector), model=self.model_name)


class RuleCaptioner:
    """Use the title the uploader already typed."""

    def caption(
        self,
        data: bytes,
        filename: str,
        title: str,
        tags: list[str],
        mime: str = "application/octet-stream",
    ) -> CaptionResult:
        del data, mime
        stem = Path(filename).stem.replace("-", " ").replace("_", " ").strip()
        return CaptionResult(caption=title or stem or "untitled", tags=list(tags))


class CompatibleEmbedder:
    def __init__(self, settings: Settings, fallback: HashEmbedder) -> None:
        self.settings = settings
        self.fallback = fallback
        self.model_name = settings.embed_model

    def embed_text(self, text: str) -> Embedding:
        try:
            response = httpx.post(
                f"{self.settings.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json={"model": self.settings.embed_model, "input": text},
                timeout=20,
            )
            response.raise_for_status()
            vector = response.json()["data"][0]["embedding"]
            if not isinstance(vector, list) or not vector:
                raise ValueError("empty embedding")
            return Embedding(
                vector=l2_normalize([float(item) for item in vector]),
                model=self.settings.embed_model,
            )
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return self.fallback.embed_text(text)


class CompatibleCaptioner:
    def __init__(self, settings: Settings, fallback: RuleCaptioner) -> None:
        self.settings = settings
        self.fallback = fallback

    def caption(self, data: bytes, filename: str, title: str, tags: list[str], mime: str) -> CaptionResult:
        prompt = (
            "Describe this meme for search. Return JSON only: "
            '{"caption":"中文一句话","caption_en":"one English sentence","tags":["tag"]}. '
            "Use 4 to 8 short tags in Chinese and English."
        )
        encoded = base64.b64encode(data).decode("ascii")
        try:
            response = httpx.post(
                f"{self.settings.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json={
                    "model": self.settings.caption_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:{mime};base64,{encoded}"},
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                },
                timeout=40,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = parse_caption_payload(content)
            if parsed is None:
                raise ValueError("caption JSON missing")
            merged = _merge_tags(tags, parsed.tags)
            return CaptionResult(caption=parsed.caption, caption_en=parsed.caption_en, tags=merged)
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return self.fallback.caption(data, filename, title, tags, mime)


def parse_caption_payload(text: str) -> CaptionResult | None:
    data = extract_json(text)
    if not data:
        return None
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []
    caption = str(data.get("caption") or "").strip()
    caption_en = str(data.get("caption_en") or "").strip()
    if not caption and not caption_en:
        return None
    return CaptionResult(
        caption=caption,
        caption_en=caption_en,
        tags=[str(tag).strip() for tag in tags if str(tag).strip()],
    )


def extract_json(text: str) -> dict | None:
    fenced = _JSON_FENCE.search(text)
    raw = fenced.group(1) if fenced else text
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def clean_rewrite(text: str, original: str) -> str:
    if not text.strip():
        return original
    line = text.strip().splitlines()[0].strip().strip("`").strip().strip('"').strip("'")
    if not line or len(line) > 200:
        return original
    return line


def rewrite_query(query: str, settings: Settings) -> str:
    if not settings.agent_enabled or not settings.api_key or not query.strip():
        return query
    try:
        response = httpx.post(
            f"{settings.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.api_key}"},
            json={
                "model": settings.rewrite_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Rewrite the user's meme search into one short keyword line. "
                            "Keep the user's language. Output one line only."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
            },
            timeout=15,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return clean_rewrite(str(content), query)
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return query


def _merge_tags(user_tags: list[str], model_tags: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for tag in [*user_tags, *model_tags]:
        cleaned = tag.strip()
        if not cleaned or cleaned.casefold() in seen:
            continue
        seen.add(cleaned.casefold())
        merged.append(cleaned)
    return merged
