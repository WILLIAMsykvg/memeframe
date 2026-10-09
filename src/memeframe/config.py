"""Environment settings. A real .env overrides nothing that is already set."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    home: Path
    db_path: Path
    library_dir: Path
    agent_enabled: bool
    api_key: str
    base_url: str
    caption_model: str
    embed_model: str
    rewrite_model: str
    image_proxy_url: str
    http_source_url: str
    http_source_header: str
    source_timeout_s: float
    max_upload_bytes: int


def get_settings() -> Settings:
    if os.environ.get("MEMEFRAME_SKIP_DOTENV") != "1":
        load_dotenv(Path.cwd() / ".env")
    home = Path(os.environ.get("MEMEFRAME_HOME", "data")).resolve()
    timeout = float(os.environ.get("MEMEFRAME_SOURCE_TIMEOUT", "8"))
    return Settings(
        home=home,
        db_path=home / "memeframe.db",
        library_dir=home / "library",
        agent_enabled=os.environ.get("MEMEFRAME_AGENT", "0") == "1",
        api_key=os.environ.get("MEMEFRAME_API_KEY", "").strip(),
        base_url=os.environ.get(
            "MEMEFRAME_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).rstrip("/"),
        caption_model=os.environ.get("MEMEFRAME_CAPTION_MODEL", "qwen-vl-plus"),
        embed_model=os.environ.get("MEMEFRAME_EMBED_MODEL", "text-embedding-v3"),
        rewrite_model=os.environ.get("MEMEFRAME_REWRITE_MODEL", "qwen-turbo"),
        image_proxy_url=os.environ.get("IMAGE_PROXY_URL", "").strip(),
        http_source_url=os.environ.get("MEMEFRAME_HTTP_SOURCE_URL", "").strip(),
        http_source_header=os.environ.get("MEMEFRAME_HTTP_SOURCE_HEADER", "").strip(),
        source_timeout_s=timeout,
        max_upload_bytes=int(os.environ.get("MEMEFRAME_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024))),
    )
