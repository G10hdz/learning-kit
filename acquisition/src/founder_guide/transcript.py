from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class NoCaptionError(LookupError):
    """No manual or automatic caption available."""

    def __init__(self, video_id: str) -> None:
        self.video_id = video_id
        self.error_code = "no_caption"
        super().__init__(f"no caption for {video_id}")


@dataclass(frozen=True)
class Transcript:
    video_id: str
    language: str
    url: str
    kind: str
    cues: tuple[dict[str, Any], ...]
    title: str = ""


class TranscriptProvider(Protocol):
    def fetch(self, video_id: str, languages: list[str]) -> Transcript: ...


class FixtureTranscriptProvider:
    """Offline transcripts. Prefer manual, then automatic. No network."""

    def __init__(self, path: Path | str) -> None:
        payload = json.loads(Path(path).read_text())
        self._videos: dict[str, dict[str, Any]] = {
            str(video_id): entry for video_id, entry in payload["videos"].items()
        }

    def fetch(self, video_id: str, languages: list[str]) -> Transcript:
        if not languages:
            raise ValueError("languages required")
        entry = self._videos.get(video_id)
        if entry is None:
            raise NoCaptionError(video_id)
        url = str(entry["url"])
        for kind in ("manual", "automatic"):
            by_lang = entry.get(kind) or {}
            for language in languages:
                cues = by_lang.get(language)
                if cues:
                    return Transcript(
                        video_id,
                        language,
                        url,
                        kind,
                        tuple(cues),
                    )
        raise NoCaptionError(video_id)


class YoutubeTranscriptApiProvider:
    """Captions via youtube-transcript-api. Manual first, then automatic."""

    def fetch(self, video_id: str, languages: list[str]) -> Transcript:
        if not languages:
            raise ValueError("languages required")
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import (
                NoTranscriptFound,
                TranscriptsDisabled,
                VideoUnavailable,
            )
        except ImportError as error:
            raise RuntimeError(
                "youtube-transcript-api not installed"
            ) from error

        api = YouTubeTranscriptApi()
        try:
            listing = api.list(video_id)
        except (TranscriptsDisabled, VideoUnavailable):
            raise NoCaptionError(video_id) from None
        except Exception as error:
            raise NoCaptionError(video_id) from error

        url = f"https://www.youtube.com/watch?v={video_id}"
        attempts = (
            ("manual", listing.find_manually_created_transcript),
            ("automatic", listing.find_generated_transcript),
        )
        for kind, finder in attempts:
            try:
                track = finder(languages)
            except NoTranscriptFound:
                continue
            except Exception:
                continue
            fetched = track.fetch()
            cues = tuple(
                {
                    "start": float(snippet.start),
                    "duration": float(snippet.duration),
                    "text": str(snippet.text),
                }
                for snippet in fetched
            )
            if cues:
                language = str(getattr(track, "language_code", languages[0]))
                return Transcript(video_id, language, url, kind, cues)
        raise NoCaptionError(video_id)


_VTT_TS = re.compile(
    r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})\s-->\s(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})"
)
_VTT_TAG = re.compile(r"<[^>]+>")


def _vtt_seconds(h: str | None, m: str, s: str, ms: str) -> float:
    hours = int(h or 0)
    return hours * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(text: str) -> tuple[dict[str, Any], ...]:
    """Minimal WebVTT cue parser. Stdlib only."""
    cues: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        match = None
        text_start = 0
        for index, line in enumerate(lines):
            match = _VTT_TS.search(line)
            if match:
                text_start = index + 1
                break
        if match is None or text_start >= len(lines):
            continue
        start = _vtt_seconds(match.group(1), match.group(2), match.group(3), match.group(4))
        end = _vtt_seconds(match.group(5), match.group(6), match.group(7), match.group(8))
        body = " ".join(_VTT_TAG.sub("", line) for line in lines[text_start:])
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        cues.append({"start": start, "duration": max(end - start, 0.0), "text": body})
    return tuple(cues)


class YtdlpTranscriptProvider:
    """Caption fallback via yt-dlp --write-subs. Optional binary."""

    def __init__(self, binary: str | None = None) -> None:
        self._binary = binary or shutil.which("yt-dlp") or "yt-dlp"

    def fetch(self, video_id: str, languages: list[str]) -> Transcript:
        if not languages:
            raise ValueError("languages required")
        if shutil.which(self._binary) is None and self._binary == "yt-dlp":
            raise NoCaptionError(video_id)

        url = f"https://www.youtube.com/watch?v={video_id}"
        lang_arg = ",".join(languages)
        with tempfile.TemporaryDirectory(prefix="guide-subs-") as tmp:
            out_tmpl = str(Path(tmp) / "sub")
            cmd = [
                self._binary,
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-langs",
                lang_arg,
                "--sub-format",
                "vtt",
                "-o",
                out_tmpl,
                url,
            ]
            try:
                subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise NoCaptionError(video_id) from error

            # Prefer manual-looking files (no .auto.) then auto.
            files = sorted(Path(tmp).glob("*.vtt"))
            if not files:
                raise NoCaptionError(video_id)
            manual = [path for path in files if ".auto." not in path.name]
            ordered = manual + [path for path in files if path not in manual]
            for path in ordered:
                cues = parse_vtt(path.read_text(encoding="utf-8", errors="replace"))
                if not cues:
                    continue
                kind = "automatic" if ".auto." in path.name else "manual"
                language = languages[0]
                for code in languages:
                    if f".{code}." in path.name or path.name.endswith(f".{code}.vtt"):
                        language = code
                        break
                return Transcript(video_id, language, url, kind, cues)
        raise NoCaptionError(video_id)


class ChainTranscriptProvider:
    """Try providers in order. First success wins."""

    def __init__(self, providers: list[TranscriptProvider]) -> None:
        if not providers:
            raise ValueError("providers required")
        self._providers = list(providers)

    def fetch(self, video_id: str, languages: list[str]) -> Transcript:
        last: Exception | None = None
        for provider in self._providers:
            try:
                return provider.fetch(video_id, languages)
            except NoCaptionError as error:
                last = error
            except Exception as error:
                last = error
        if isinstance(last, NoCaptionError):
            raise last
        raise NoCaptionError(video_id)


class TranscriptApiProvider:
    """Captions via transcriptapi.com REST API. Needs TRANSCRIPT_API_KEY."""

    BASE_URL = "https://transcriptapi.com/api/v2"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout: float = 30.0,
        client: Any | None = None,
    ) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError("api_key required")
        self._api_key = key
        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._timeout = timeout
        self._client = client

    def fetch(self, video_id: str, languages: list[str]) -> Transcript:
        if not languages:
            raise ValueError("languages required")
        try:
            import httpx
        except ImportError as error:
            raise RuntimeError("httpx not installed") from error

        # Prefer creator track, then ASR, per language priority.
        lang_parts: list[str] = []
        for code in languages:
            code = code.strip()
            if not code:
                continue
            lang_parts.append(code)
            if not code.startswith("asr"):
                lang_parts.append(f"asr-{code}")
        params = {
            "video_url": video_id,
            "format": "json",
            "include_timestamp": "true",
            "language": ",".join(lang_parts) if lang_parts else languages[0],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self._base_url}/youtube/transcript"
        try:
            if self._client is not None:
                response = self._client.get(
                    url, params=params, headers=headers, timeout=self._timeout
                )
            else:
                response = httpx.get(
                    url, params=params, headers=headers, timeout=self._timeout
                )
        except Exception as error:
            raise NoCaptionError(video_id) from error

        if response.status_code in {401, 402}:
            raise RuntimeError(
                f"TranscriptAPI auth/billing HTTP {response.status_code}"
            )
        if response.status_code == 404:
            raise NoCaptionError(video_id)
        if response.status_code != 200:
            raise NoCaptionError(video_id)

        try:
            payload = response.json()
        except Exception as error:
            raise NoCaptionError(video_id) from error

        rows = payload.get("transcript") or []
        cues: list[dict[str, Any]] = []
        for row in rows:
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            try:
                start = float(row.get("start", 0.0))
                duration = float(row.get("duration", 0.0))
            except (TypeError, ValueError):
                continue
            cues.append({"start": start, "duration": duration, "text": text})
        if not cues:
            raise NoCaptionError(video_id)

        resolved = str(payload.get("language") or languages[0])
        kind = "automatic" if resolved.startswith("asr") else "manual"
        language = resolved.removeprefix("asr-") if resolved.startswith("asr-") else resolved
        if language == "asr":
            language = languages[0]
        title = str(payload.get("title") or "").strip()
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        return Transcript(video_id, language, watch_url, kind, tuple(cues), title)


def default_live_transcript_provider() -> TranscriptProvider:
    key = (
        os.environ.get("TRANSCRIPT_API_KEY", "").strip()
        or os.environ.get("GUIDE_TRANSCRIPT_API_KEY", "").strip()
    )
    if key:
        # Prefer managed API when configured; skips local IP bans.
        return TranscriptApiProvider(key)
    return ChainTranscriptProvider(
        [YoutubeTranscriptApiProvider(), YtdlpTranscriptProvider()]
    )
