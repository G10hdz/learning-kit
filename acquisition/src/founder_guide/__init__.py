from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .catalog import (
    CatalogProvider,
    FixtureCatalogProvider,
    Source,
    YtdlpCatalogProvider,
    collect_sources,
    resolve_title_oembed,
)
from .store import SqliteStore
from .transcript import (
    ChainTranscriptProvider,
    FixtureTranscriptProvider,
    NoCaptionError,
    Transcript,
    TranscriptApiProvider,
    TranscriptProvider,
    YoutubeTranscriptApiProvider,
    YtdlpTranscriptProvider,
    default_live_transcript_provider,
    parse_vtt,
)

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"\w+", re.UNICODE)


def _configured_scopes() -> frozenset[str]:
    """Scopes from GUIDE_SCOPES env, always includes 'shared'."""
    import os

    raw = os.environ.get("GUIDE_SCOPES", "").strip()
    scopes: set[str] = {"shared"}
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if part:
                scopes.add(part)
    return frozenset(scopes)
_STAGES = frozenset(
    {"idea", "validation", "mvp", "pmf", "growth", "fundraising", "team", ""}
)


@dataclass(frozen=True)
class Cue:
    start: float
    duration: float
    text: str

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass(frozen=True)
class Segment:
    citation_id: str
    video_id: str
    language: str
    url: str
    start_seconds: int
    end_seconds: int
    text: str


@dataclass(frozen=True)
class SearchHit:
    citation_id: str
    url: str
    start_seconds: int
    text: str
    score: float
    title: str = ""


@dataclass(frozen=True)
class Citation:
    citation_id: str
    url: str
    start_seconds: int
    title: str = ""


@dataclass(frozen=True)
class Answer:
    text: str
    citations: tuple[Citation, ...]
    insufficient_evidence: bool


@dataclass(frozen=True)
class IngestResult:
    transcript_hash: str
    segments: tuple[Segment, ...]
    created: bool
    transcript_kind: str


@dataclass(frozen=True)
class Note:
    note_id: str
    video_id: str
    scope: str
    content: str
    stage: str
    url: str


def normalize_cues(raw_cues: list[dict[str, Any]]) -> list[Cue]:
    cues: list[Cue] = []
    previous = ""
    for raw in sorted(raw_cues, key=lambda item: float(item["start"])):
        start, duration = float(raw["start"]), float(raw["duration"])
        if start < 0 or duration <= 0:
            raise ValueError("timestamps must be non-negative with positive duration")
        text = _SPACE.sub(" ", _TAG.sub(" ", html.unescape(str(raw["text"])))).strip()
        if not text or text == previous:
            continue
        if previous and text.startswith(previous + " "):
            text = text[len(previous) :].strip()
        cues.append(Cue(start, duration, text))
        previous = _SPACE.sub(" ", _TAG.sub(" ", html.unescape(str(raw["text"])))).strip()
    if not cues:
        raise ValueError("transcript has no usable cues")
    return cues


def segment_cues(cues: list[Cue]) -> list[list[Cue]]:
    batches: list[list[Cue]] = []
    batch: list[Cue] = []
    for cue in cues:
        if cue.duration > 120:
            raise ValueError("a cue cannot exceed 120 seconds")
        if batch and cue.end - batch[0].start > 120:
            if batch[-1].end - batch[0].start < 60:
                raise ValueError("timestamps cannot form a 60-120 second segment")
            batches.append(batch)
            batch = []
        batch.append(cue)
        duration = batch[-1].end - batch[0].start
        if duration >= 60 and (cue.text.endswith((".", "!", "?")) or duration >= 120):
            batches.append(batch)
            batch = []
    if batch:
        if batch[-1].end - batch[0].start >= 60:
            batches.append(batch)
        elif batches:
            # ponytail: merge short tail into previous segment even if >120s
            batches[-1].extend(batch)
        else:
            raise ValueError("transcript cannot form a 60-120 second segment")
    return batches


class Guide:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self._documents: dict[tuple[str, str, str], tuple[Segment, ...]] = {}
        self._kinds: dict[tuple[str, str, str], str] = {}
        self._active: dict[tuple[str, str], str] = {}
        self._sources: dict[str, Source] = {}
        self._notes: dict[str, Note] = {}
        self._urls: dict[str, str] = {}
        self._titles: dict[str, str] = {}
        self._store = SqliteStore(db_path) if db_path is not None else None
        if self._store is not None:
            snapshot = self._store.load()
            self._sources = snapshot["sources"]
            self._documents = snapshot["documents"]
            self._kinds = snapshot["kinds"]
            self._active = snapshot["active"]
            self._notes = snapshot["notes"]
            self._urls = snapshot["urls"]
            self._titles = {
                video_id: source.title
                for video_id, source in self._sources.items()
                if source.title
            }

    @property
    def document_count(self) -> int:
        return len(self._documents)

    @property
    def segment_count(self) -> int:
        return sum(len(segments) for segments in self._documents.values())

    @property
    def source_count(self) -> int:
        return len(self._sources)

    @property
    def sources(self) -> tuple[Source, ...]:
        return tuple(self._sources.values())

    @property
    def notes(self) -> tuple[Note, ...]:
        return tuple(self._notes.values())

    def catalog_channel(
        self,
        provider: CatalogProvider,
        channel: str,
        limit: int = 20,
    ) -> tuple[Source, ...]:
        collected = collect_sources(provider, channel, limit)
        for source in collected:
            title = source.title
            if not title:
                title = resolve_title_oembed(source.video_id)
            if title and title != source.title:
                source = Source(
                    source.video_id, source.url, source.published_at, title
                )
            self._sources[source.video_id] = source
            self._urls[source.video_id] = source.url
            if source.title:
                self._titles[source.video_id] = source.title
            if self._store is not None:
                self._store.upsert_source(source)
        return collected

    def ingest_video(
        self,
        provider: TranscriptProvider,
        video_id: str,
        languages: list[str],
    ) -> IngestResult:
        fetched = provider.fetch(video_id, languages)
        return self.ingest(
            {
                "video_id": fetched.video_id,
                "language": fetched.language,
                "url": fetched.url,
                "kind": fetched.kind,
                "cues": list(fetched.cues),
                "title": fetched.title,
            }
        )

    def ingest(self, transcript: dict[str, Any]) -> IngestResult:
        video_id = str(transcript["video_id"])
        language = str(transcript["language"])
        url = str(transcript["url"])
        kind = str(transcript.get("kind", "manual"))
        title = str(transcript.get("title") or "").strip()
        if title:
            self._titles[video_id] = title
        if kind not in {"manual", "automatic"}:
            raise ValueError("transcript kind must be manual or automatic")
        cues = normalize_cues(transcript["cues"])
        canonical = [[cue.start, cue.duration, cue.text] for cue in cues]
        digest = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        key = (video_id, language, digest)
        if key in self._documents:
            self._active[(video_id, language)] = digest
            if self._store is not None:
                self._store.upsert_document(
                    video_id,
                    language,
                    digest,
                    self._kinds[key],
                    self._documents[key],
                    active=True,
                )
            return IngestResult(
                digest, self._documents[key], False, self._kinds[key]
            )

        segments = []
        for position, batch in enumerate(segment_cues(cues)):
            citation_id = "seg_" + hashlib.sha256(
                f"{video_id}:{language}:{digest}:{position}".encode()
            ).hexdigest()[:16]
            segments.append(
                Segment(
                    citation_id,
                    video_id,
                    language,
                    url,
                    int(batch[0].start),
                    int(batch[-1].end),
                    " ".join(cue.text for cue in batch),
                )
            )
        stored = tuple(segments)
        self._documents[key] = stored
        self._kinds[key] = kind
        self._active[(video_id, language)] = digest
        self._urls[video_id] = url
        if self._store is not None:
            self._store.upsert_document(
                video_id, language, digest, kind, stored, active=True
            )
        return IngestResult(digest, stored, True, kind)

    def ingest_pending(
        self,
        provider: TranscriptProvider,
        languages: list[str],
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if not languages:
            raise ValueError("languages required")
        ingested = {video_id for video_id, _language in self._active}
        report: list[dict[str, Any]] = []
        for source in self._sources.values():
            if len(report) >= limit:
                break
            if source.video_id in ingested:
                continue
            try:
                result = self.ingest_video(provider, source.video_id, languages)
            except NoCaptionError as error:
                report.append(
                    {
                        "video_id": source.video_id,
                        "status": error.error_code,
                    }
                )
                continue
            except ValueError:
                # shorts / broken captions that cannot form 60-120s segments
                report.append(
                    {
                        "video_id": source.video_id,
                        "status": "invalid_transcript",
                    }
                )
                continue
            ingested.add(source.video_id)
            report.append(
                {
                    "video_id": source.video_id,
                    "status": "ingested" if result.created else "exists",
                    "transcript_kind": result.transcript_kind,
                    "transcript_hash": result.transcript_hash,
                    "segment_count": len(result.segments),
                }
            )
        return report

    def add_note(
        self,
        video_id: str,
        scope: str,
        content: str,
        stage: str = "",
        url: str = "",
    ) -> Note:
        if scope not in _configured_scopes():
            raise ValueError(f"invalid scope '{scope}'")
        if stage not in _STAGES:
            raise ValueError("invalid stage")
        text = _SPACE.sub(" ", content).strip()
        if not text:
            raise ValueError("note content required")
        resolved = url or self._urls.get(video_id) or (
            self._sources[video_id].url if video_id in self._sources else ""
        )
        if not resolved:
            raise ValueError("note requires a known video url")
        note_id = "note_" + hashlib.sha256(
            f"{video_id}:{scope}:{stage}:{text}".encode()
        ).hexdigest()[:16]
        note = Note(note_id, video_id, scope, text, stage, resolved)
        self._notes[note_id] = note
        if self._store is not None:
            self._store.upsert_note(note)
        return note

    def search(
        self,
        query: str,
        limit: int = 10,
        scope: str = "shared",
        stage: str = "",
    ) -> list[SearchHit]:
        if scope not in _configured_scopes():
            raise ValueError(f"invalid scope '{scope}'")
        if stage not in _STAGES:
            raise ValueError("invalid stage")
        terms = set(_WORD.findall(query.casefold()))
        if not terms:
            return []
        ranked: list[tuple[str, SearchHit]] = []
        for (video_id, language), digest in self._active.items():
            for segment in self._documents[(video_id, language, digest)]:
                overlap = terms & set(_WORD.findall(segment.text.casefold()))
                if overlap:
                    ranked.append(
                        (
                            video_id,
                            SearchHit(
                                segment.citation_id,
                                segment.url,
                                segment.start_seconds,
                                segment.text,
                                len(overlap) / len(terms),
                                self._titles.get(video_id, ""),
                            ),
                        )
                    )
        for note in self._notes.values():
            if note.scope != "shared" and note.scope != scope:
                continue
            if stage and note.stage != stage:
                continue
            overlap = terms & set(_WORD.findall(note.content.casefold()))
            if overlap:
                ranked.append(
                    (
                        note.video_id,
                        SearchHit(
                            note.note_id,
                            note.url,
                            0,
                            note.content,
                            len(overlap) / len(terms),
                            self._titles.get(note.video_id, ""),
                        ),
                    )
                )
        ranked.sort(key=lambda item: (-item[1].score, item[1].citation_id))
        # Spec: at most 3 hits per source so one video cannot dominate.
        per_source = 3
        counts: dict[str, int] = {}
        hits: list[SearchHit] = []
        for source_id, hit in ranked:
            if counts.get(source_id, 0) >= per_source:
                continue
            counts[source_id] = counts.get(source_id, 0) + 1
            hits.append(hit)
            if len(hits) >= limit:
                break
        return hits

    def answer(
        self,
        question: str,
        limit: int = 10,
        scope: str = "shared",
        stage: str = "",
        synthesizer: "Synthesizer | None" = None,
    ) -> Answer:
        hits = self.search(question, limit=limit, scope=scope, stage=stage)
        insufficient_evidence = len(hits) < 2
        citations = tuple(
            Citation(
                hit.citation_id,
                f"{hit.url}&t={hit.start_seconds}s",
                hit.start_seconds,
                hit.title,
            )
            for hit in hits
        )
        if insufficient_evidence:
            return Answer("", citations, True)
        if synthesizer is not None:
            from .synthesis import ExtractiveSynthesizer

            passages = [(i + 1, hit.text) for i, hit in enumerate(hits)]
            try:
                text = synthesizer.synthesize(question, passages)
            except Exception:
                text = ExtractiveSynthesizer().synthesize(question, passages)
        else:
            text = " ".join(hit.text for hit in hits)
        return Answer(text, citations, False)

    def verify_corpus(self) -> dict[str, Any]:
        issues: list[dict[str, str]] = []
        for (video_id, language), digest in self._active.items():
            key = (video_id, language, digest)
            segments = self._documents.get(key)
            if segments is None:
                issues.append(
                    {
                        "code": "missing_document",
                        "detail": f"{video_id}:{language}:{digest[:8]}",
                    }
                )
                continue
            if not segments:
                issues.append(
                    {
                        "code": "empty_segments",
                        "detail": f"{video_id}:{language}",
                    }
                )
            for segment in segments:
                if not segment.url:
                    issues.append(
                        {
                            "code": "segment_missing_url",
                            "detail": segment.citation_id,
                        }
                    )
                if segment.end_seconds <= segment.start_seconds:
                    issues.append(
                        {
                            "code": "bad_timestamp",
                            "detail": segment.citation_id,
                        }
                    )
                span = segment.end_seconds - segment.start_seconds
                # segment_cues closes every batch in (60, 120]; the documented
                # tail merge only bloats the LAST segment past 120, so a
                # non-final over-length segment is the real corruption signal.
                if span < 60 or (span > 120 and segment is not segments[-1]):
                    issues.append(
                        {
                            "code": "segment_out_of_range",
                            "detail": segment.citation_id,
                        }
                    )
        for note in self._notes.values():
            if not note.url or not note.content:
                issues.append({"code": "bad_note", "detail": note.note_id})
            if note.scope not in _configured_scopes():
                issues.append({"code": "bad_note_scope", "detail": note.note_id})
        return {
            "ok": not issues,
            "sources": self.source_count,
            "documents": self.document_count,
            "segments": self.segment_count,
            "notes": len(self._notes),
            "active": len(self._active),
            "issues": issues,
        }


def load_dotenv(path: Path | str | None = None) -> None:
    """Load KEY=VAL from .env into os.environ if key not already set."""
    import os

    env_path = Path(path) if path is not None else Path.cwd() / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def main() -> None:
    import argparse
    from importlib.resources import files

    load_dotenv()
    parser = argparse.ArgumentParser(prog="guide")
    parser.add_argument(
        "command",
        choices=[
            "demo",
            "catalog-channel",
            "ingest-video",
            "ingest-pending",
            "ingest-book",
            "rebuild-index",
            "search",
            "q",
            "add-note",
            "serve",
            "verify-corpus",
        ],
    )
    parser.add_argument("target", nargs="?", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--languages", default="es")
    parser.add_argument("--scope", default="shared")
    parser.add_argument("--stage", default="")
    parser.add_argument("--content", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--token", default="")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--catalog-fixture", type=Path)
    parser.add_argument("--transcript-fixture", type=Path)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--vault", type=Path, default=Path("vault"))
    parser.add_argument("--book-id", default="")
    parser.add_argument("--section", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--license", default="private")
    parser.add_argument("--language", default="es")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use real YouTube providers (network).",
    )
    args = parser.parse_args()
    package = files("founder_guide")
    languages = [part.strip() for part in args.languages.split(",") if part.strip()]

    def make_guide() -> Guide:
        return Guide(db_path=args.db)

    def catalog_provider() -> CatalogProvider:
        if args.catalog_fixture is not None:
            return FixtureCatalogProvider(args.catalog_fixture)
        if args.live:
            return YtdlpCatalogProvider()
        catalog_path = args.fixture or Path(
            str(package.joinpath("demo_catalog.json"))
        )
        return FixtureCatalogProvider(catalog_path)

    def transcript_provider() -> TranscriptProvider:
        if args.transcript_fixture is not None:
            return FixtureTranscriptProvider(args.transcript_fixture)
        if args.live:
            return default_live_transcript_provider()
        # serve uses --fixture for seed doc; catalog/ingest may reuse it
        if args.command in {"ingest-video", "ingest-pending"} and args.fixture:
            return FixtureTranscriptProvider(args.fixture)
        return FixtureTranscriptProvider(
            Path(str(package.joinpath("demo_transcripts.json")))
        )

    if args.command == "catalog-channel":
        channel = args.target or "https://www.youtube.com/@demo"
        provider = catalog_provider()
        guide = make_guide()
        sources = guide.catalog_channel(provider, channel, args.limit)
        print(
            json.dumps(
                {
                    "channel": channel,
                    "limit": args.limit,
                    "count": len(sources),
                    "sources": [source.__dict__ for source in sources],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "ingest-video":
        video_id = args.target or "demo-auto-only"
        provider = transcript_provider()
        guide = make_guide()
        result = guide.ingest_video(provider, video_id, languages)
        print(
            json.dumps(
                {
                    "video_id": video_id,
                    "languages": languages,
                    "transcript_kind": result.transcript_kind,
                    "transcript_hash": result.transcript_hash,
                    "created": result.created,
                    "segment_count": len(result.segments),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "ingest-pending":
        channel = args.target or "https://www.youtube.com/@demo"
        guide = make_guide()
        guide.catalog_channel(catalog_provider(), channel, args.limit)
        report = guide.ingest_pending(
            transcript_provider(), languages, args.limit
        )
        print(
            json.dumps(
                {
                    "channel": channel,
                    "limit": args.limit,
                    "languages": languages,
                    "processed": len(report),
                    "results": report,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "ingest-book":
        from .book import ingest_file

        file_path = Path(args.target)
        if not file_path.is_file():
            print(f"archivo no encontrado: {file_path}")
            return
        book_id = args.book_id or file_path.stem
        section = args.section or "01-startup-negocio"
        title = args.title or file_path.stem
        author = args.author or ""
        vault_path = args.vault
        written = ingest_file(
            file_path,
            vault_path,
            book_id=book_id,
            section=section,
            title=title,
            author=author,
            license=args.license,
            language=args.language,
        )
        print(
            json.dumps(
                {
                    "file": str(file_path),
                    "book_id": book_id,
                    "section": section,
                    "title": title,
                    "vault": str(vault_path),
                    "written": written,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "rebuild-index":
        from .index import rebuild_index

        if args.db is None:
            print("rebuild-index requiere --db")
            return
        rebuild_index(args.vault, args.db)
        print(
            json.dumps(
                {"vault": str(args.vault), "db": str(args.db), "ok": True},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command in {"search", "q"}:
        from .query import answer_knowledge, hit_to_dict, search_knowledge

        if args.db is None:
            print(f"{args.command} requiere --db")
            return
        query = args.target.strip()
        if not query:
            print(f"{args.command} requiere QUERY")
            return
        if args.command == "search":
            hits = search_knowledge(
                args.db, query, scope=args.scope, limit=args.limit
            )
            print(
                json.dumps(
                    {
                        "query": query,
                        "scope": args.scope,
                        "count": len(hits),
                        "hits": [hit_to_dict(hit) for hit in hits],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        answer = answer_knowledge(
            args.db, query, scope=args.scope, limit=args.limit
        )
        print(
            json.dumps(
                {
                    "query": query,
                    "scope": args.scope,
                    "answer": answer.text,
                    "insufficient_evidence": answer.insufficient_evidence,
                    "citations": [c.__dict__ for c in answer.citations],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    if args.command == "add-note":
        video_id = args.target or "demo-founder-001"
        guide = make_guide()
        note = guide.add_note(
            video_id,
            args.scope,
            args.content,
            stage=args.stage,
            url=args.url
            or f"https://youtube.com/watch?v={video_id}",
        )
        print(json.dumps(note.__dict__, ensure_ascii=False, indent=2))
        return

    if args.command == "serve":
        from .http_api import serve

        guide = make_guide()
        if guide.document_count == 0 and not args.live:
            path = args.fixture or Path(
                str(package.joinpath("demo_transcript.json"))
            )
            guide.ingest(json.loads(path.read_text()))
        from .synthesis import default_synthesizer

        serve(
            guide,
            host=args.host,
            port=args.port,
            token=args.token or None,
            transcript_provider=transcript_provider(),
            synthesizer=default_synthesizer(),
        )
        return

    if args.command == "verify-corpus":
        guide = make_guide()
        if guide.document_count == 0 and not args.db:
            path = args.fixture or Path(
                str(package.joinpath("demo_transcript.json"))
            )
            guide.ingest(json.loads(path.read_text()))
        print(json.dumps(guide.verify_corpus(), ensure_ascii=False, indent=2))
        return

    if args.fixture:
        transcript = json.loads(args.fixture.read_text())
    else:
        transcript = json.loads(
            package.joinpath("demo_transcript.json").read_text()
        )
    guide = make_guide()
    result = guide.ingest(transcript)
    question = "¿Cómo validar con usuarios?"
    answer = guide.answer(question)
    print(
        json.dumps(
            {
                "video_id": transcript["video_id"],
                "question": question,
                "answer": answer.text,
                "transcript_hash": result.transcript_hash,
                "transcript_kind": result.transcript_kind,
                "citations": [citation.__dict__ for citation in answer.citations],
                "insufficient_evidence": answer.insufficient_evidence,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


__all__ = [
    "Answer",
    "CatalogProvider",
    "Citation",
    "FixtureCatalogProvider",
    "FixtureTranscriptProvider",
    "Guide",
    "IngestResult",
    "NoCaptionError",
    "Note",
    "SearchHit",
    "Segment",
    "Source",
    "SqliteStore",
    "Transcript",
    "TranscriptProvider",
    "main",
    "normalize_cues",
    "segment_cues",
]


def __getattr__(name: str):
    if name == "create_app":
        from .http_api import create_app

        return create_app
    raise AttributeError(name)
