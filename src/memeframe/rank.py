"""Rank text overlap. Chinese bigrams and Latin words share one scorer."""

from __future__ import annotations

import math
import re

from memeframe.models import Meme

_WORD = re.compile(r"[a-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokens(text: str) -> set[str]:
    lowered = text.lower()
    words = set(_WORD.findall(lowered))
    chars = _CJK.findall(lowered)
    grams = set(chars)
    grams.update("".join(chars[i : i + 2]) for i in range(len(chars) - 1))
    return words | grams


def meme_text(meme: Meme) -> str:
    return "\n".join(
        [
            meme.title,
            meme.title_en,
            meme.caption,
            meme.caption_en,
            " ".join(meme.tags),
        ]
    )


def text_score(query: str, meme: Meme) -> float:
    wanted = tokens(query)
    if not wanted:
        return 0.0
    found = tokens(meme_text(meme))
    if not found:
        return 0.0
    overlap = len(wanted & found)
    if overlap == 0:
        return 0.0
    return overlap / len(wanted)


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(1.0, dot))


def combine(keyword: float, vector: float) -> float:
    if keyword <= 0 and vector <= 0:
        return 0.0
    if vector <= 0:
        return keyword
    if keyword <= 0:
        return 0.3 * vector
    return 0.7 * keyword + 0.3 * vector


def l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]
