"""Built-in scenes so search works before anyone uploads.

这些是原创占位图，不是从别的站点抓来的梗图。
"""

from __future__ import annotations

from html import escape

from memeframe.models import Meme, SearchOptions
from memeframe.rank import text_score
from memeframe.sources.base import Source

_CATALOG: list[dict[str, object]] = [
    {
        "id": "starter-pie",
        "title": "画饼",
        "title_en": "Empty promise",
        "caption": "老板在白板上画了一个大饼，说这是下个季度的计划。",
        "caption_en": "A boss draws a pie on the whiteboard and calls it next quarter's plan.",
        "tags": ["画饼", "老板", "加班", "promise", "boss"],
    },
    {
        "id": "starter-awkward",
        "title": "社死",
        "title_en": "Awkward silence",
        "caption": "会上说错一句话，全场安静。",
        "caption_en": "One wrong sentence in the meeting, then total silence.",
        "tags": ["社死", "尴尬", "会议", "awkward"],
    },
    {
        "id": "starter-offwork",
        "title": "下班",
        "title_en": "Off work",
        "caption": "时钟一到六点，人已经转向电梯。",
        "caption_en": "The clock hits six and everyone turns toward the elevator.",
        "tags": ["下班", "六点", "elevator"],
    },
    {
        "id": "starter-sarcasm",
        "title": "阴阳怪气",
        "title_en": "Backhanded praise",
        "caption": "一句“你好厉害哦”，配上假笑。",
        "caption_en": "A flat wow, amazing, with a fake smile.",
        "tags": ["阴阳怪气", "假笑", "sarcasm"],
    },
    {
        "id": "starter-cat",
        "title": "无语的猫",
        "title_en": "Speechless cat",
        "caption": "一只猫盯着镜头，脸上什么表情都没有。",
        "caption_en": "A cat stares at the camera with a completely blank face.",
        "tags": ["猫", "无语", "cat", "speechless"],
    },
    {
        "id": "starter-friday",
        "title": "周五了",
        "title_en": "Friday",
        "caption": "周五下午，椅子已经对着门口。",
        "caption_en": "Friday afternoon, the chair is already pointed at the door.",
        "tags": ["周五", "下班", "friday"],
    },
]


def starter_memes() -> list[Meme]:
    memes: list[Meme] = []
    for index, item in enumerate(_CATALOG):
        meme_id = str(item["id"])
        memes.append(
            Meme(
                id=meme_id,
                title=str(item["title"]),
                title_en=str(item["title_en"]),
                caption=str(item["caption"]),
                caption_en=str(item["caption_en"]),
                tags=list(item["tags"]),  # type: ignore[arg-type]
                url=f"/media/starter/{meme_id}.svg",
                source_id="starter",
                format="svg",
                score=0.1,
                created_at=f"2026-01-01T00:00:0{index}+00:00",
            )
        )
    return memes


def starter_by_id(meme_id: str) -> Meme | None:
    for meme in starter_memes():
        if meme.id == meme_id:
            return meme
    return None


def svg_for(meme: Meme) -> str:
    title = escape(meme.title)
    subtitle = escape(meme.caption[:42])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">
  <rect width="640" height="480" fill="#f6f3ec"/>
  <rect x="28" y="28" width="584" height="424" fill="#fffdf8" stroke="#1c1915" stroke-width="4"/>
  <text x="52" y="210" fill="#c2410c" font-size="64" font-family="sans-serif">{title}</text>
  <text x="52" y="270" fill="#1c1915" font-size="22" font-family="sans-serif">{subtitle}</text>
</svg>
"""


class StarterPackSource(Source):
    id = "starter"
    name = "起步包 · Starter pack"
    description = "原创占位场景，用来在空库时演示搜索。Original placeholder scenes for an empty library."
    requires_auth = False
    enabled = True

    def search(self, keyword: str, options: SearchOptions) -> list[Meme]:
        found: list[Meme] = []
        for meme in starter_memes():
            if not keyword.strip():
                meme.score = 0.1
                found.append(meme)
                continue
            score = text_score(keyword, meme)
            if score <= 0:
                continue
            meme.score = score
            found.append(meme)
        found.sort(key=lambda meme: meme.score, reverse=True)
        return found[: options.limit]
