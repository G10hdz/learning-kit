from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Source:
    video_id: str
    url: str
    published_at: str
    title: str = ""


@dataclass(frozen=True)
class Page:
    items: tuple[Source, ...]
    next_cursor: str | None


class CatalogProvider(Protocol):
    def list_videos(self, channel: str, cursor: str | None) -> Page: ...


def resolve_title_oembed(video_id: str, *, timeout: float = 8.0) -> str:
    """Best-effort video title via YouTube oEmbed. Empty string on failure."""
    url = (
        f"https://www.youtube.com/oembed?"
        f"url=https://www.youtube.com/watch?v={video_id}&format=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                return str(data.get("title", "")).strip()
    except Exception:
        pass
    return ""


class FixtureCatalogProvider:
    """Offline catalog for tests and local demo. No network."""

    def __init__(self, path: Path | str) -> None:
        payload = json.loads(Path(path).read_text())
        self._channel = str(payload.get("channel", ""))
        self._videos = tuple(
            Source(
                str(item["video_id"]),
                str(item["url"]),
                str(item["published_at"]),
                str(item.get("title", "")),
            )
            for item in payload["videos"]
        )

    def list_videos(self, channel: str, cursor: str | None) -> Page:
        if self._channel and channel != self._channel:
            return Page((), None)
        start = int(cursor or 0)
        # ponytail: page size fixed; real API pages later
        end = min(start + 10, len(self._videos))
        items = self._videos[start:end]
        next_cursor = str(end) if end < len(self._videos) else None
        return Page(items, next_cursor)


class YtdlpCatalogProvider:
    """Channel/playlist listing via yt-dlp --flat-playlist."""

    def __init__(self, binary: str | None = None, page_size: int = 10) -> None:
        self._binary = binary or shutil.which("yt-dlp") or "yt-dlp"
        self._page_size = max(1, page_size)
        self._cache: dict[str, tuple[Source, ...]] = {}

    def list_videos(self, channel: str, cursor: str | None) -> Page:
        if shutil.which(self._binary) is None and self._binary == "yt-dlp":
            raise RuntimeError("yt-dlp not installed")
        videos = self._cache.get(channel)
        if videos is None:
            videos = self._fetch_all(channel)
            self._cache[channel] = videos
        start = int(cursor or 0)
        end = min(start + self._page_size, len(videos))
        items = videos[start:end]
        next_cursor = str(end) if end < len(videos) else None
        return Page(items, next_cursor)

    def _fetch_all(self, channel: str) -> tuple[Source, ...]:
        cmd = [
            self._binary,
            "--flat-playlist",
            "--dump-json",
            "--playlist-end",
            "50",
            channel,
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"yt-dlp failed: {error}") from error
        if proc.returncode != 0 and not proc.stdout.strip():
            raise RuntimeError(proc.stderr.strip() or "yt-dlp failed")
        sources: list[Source] = []
        seen: set[str] = set()
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            video_id = str(row.get("id") or "").strip()
            if not video_id or video_id in seen:
                continue
            url = str(row.get("url") or row.get("webpage_url") or "").strip()
            if url and not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={video_id}"
            if not url:
                url = f"https://www.youtube.com/watch?v={video_id}"
            published = str(
                row.get("upload_date")
                or row.get("release_timestamp")
                or row.get("timestamp")
                or "1970-01-01"
            )
            if len(published) == 8 and published.isdigit():
                published = f"{published[:4]}-{published[4:6]}-{published[6:]}T00:00:00Z"
            title = str(row.get("title") or "").strip()
            sources.append(Source(video_id, url, published, title))
            seen.add(video_id)
        return tuple(sources)


def collect_sources(
    provider: CatalogProvider,
    channel: str,
    limit: int = 20,
) -> tuple[Source, ...]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    unique: dict[str, Source] = {}
    cursor: str | None = None
    while len(unique) < limit:
        page = provider.list_videos(channel, cursor)
        if not page.items:
            break
        for source in page.items:
            if source.video_id in unique:
                continue
            if not source.url or not source.published_at:
                raise ValueError("source requires url and published_at")
            unique[source.video_id] = source
            if len(unique) >= limit:
                break
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
    return tuple(unique.values())
