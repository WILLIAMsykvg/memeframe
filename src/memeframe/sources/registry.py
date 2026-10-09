"""Fan out to sources. One slow source does not cancel the others."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait

from memeframe.models import Meme, SearchOptions, SearchResult
from memeframe.sources.base import Source


def dedupe(memes: list[Meme]) -> list[Meme]:
    ordered = sorted(memes, key=lambda meme: (meme.score, meme.created_at), reverse=True)
    seen: set[str] = set()
    unique: list[Meme] = []
    for meme in ordered:
        key = meme.sha256 or _canon(meme.origin_url or meme.url)
        if key:
            if key in seen:
                continue
            seen.add(key)
        unique.append(meme)
    return unique


def _canon(url: str) -> str:
    return url.split("?", 1)[0].rstrip("/").lower()


class Registry:
    def __init__(self) -> None:
        self._sources: dict[str, Source] = {}

    def register(self, source: Source) -> None:
        self._sources[source.id] = source

    def list(self) -> list[Source]:
        return list(self._sources.values())

    def search(
        self,
        keyword: str,
        source_ids: list[str] | None,
        options: SearchOptions,
    ) -> SearchResult:
        selected: list[Source] = []
        errors: dict[str, str] = {}
        if source_ids:
            for source_id in source_ids:
                source = self._sources.get(source_id)
                if source is None:
                    errors[source_id] = "source not found"
                elif not source.enabled:
                    errors[source_id] = "source is not configured"
                else:
                    selected.append(source)
        else:
            selected = [source for source in self._sources.values() if source.enabled]

        memes: list[Meme] = []
        succeeded: list[str] = []
        if selected:
            pool = ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="memeframe-source")
            futures = {pool.submit(self._run, source, keyword, options): source.id for source in selected}
            done, pending = wait(futures, timeout=options.timeout_s)
            for future in pending:
                errors[futures[future]] = "timeout"
                future.cancel()
            for future in done:
                source_id, found, error = future.result()
                if error:
                    errors[source_id] = error
                    continue
                succeeded.append(source_id)
                memes.extend(found)
            pool.shutdown(wait=False, cancel_futures=True)

        memes = dedupe(memes)
        return SearchResult(
            memes=memes,
            sources=succeeded,
            errors=errors,
            total=len(memes),
            duration_ms=0,
        )

    @staticmethod
    def _run(source: Source, keyword: str, options: SearchOptions) -> tuple[str, list[Meme], str | None]:
        try:
            return source.id, source.search(keyword, options), None
        except Exception as exc:  # source boundary: keep the other adapters
            return source.id, [], f"{type(exc).__name__}: {exc}"
