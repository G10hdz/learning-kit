from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .catalog import Source

if TYPE_CHECKING:
    from . import Note, Segment
    from .models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    video_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    published_at TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS documents (
    video_id TEXT NOT NULL,
    language TEXT NOT NULL,
    transcript_hash TEXT NOT NULL,
    transcript_kind TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (video_id, language, transcript_hash)
);
CREATE TABLE IF NOT EXISTS segments (
    citation_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    language TEXT NOT NULL,
    transcript_hash TEXT NOT NULL,
    url TEXT NOT NULL,
    start_seconds INTEGER NOT NULL,
    end_seconds INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    note_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    stage TEXT NOT NULL,
    url TEXT NOT NULL
);
"""

_V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    canonical_uri TEXT NOT NULL,
    license TEXT NOT NULL,
    permission_status TEXT NOT NULL,
    visibility_scope TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS knowledge_documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    language TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    canonical_path TEXT NOT NULL,
    version INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL,
    locator_kind TEXT NOT NULL,
    start_seconds INTEGER,
    end_seconds INTEGER,
    page_start INTEGER,
    page_end INTEGER,
    path TEXT,
    heading TEXT
);
"""


class SqliteStore:
    """Write-through store. Guide keeps working memory; this survives process exit."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.executescript("BEGIN IMMEDIATE;\n" + _SCHEMA + _V2_SCHEMA)
            self._migrate()
            self._project_v1()
            self._conn.execute("PRAGMA user_version = 2")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            self._conn.close()
            raise

    def _migrate(self) -> None:
        columns = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(sources)")
        }
        if "title" not in columns:
            self._conn.execute(
                "ALTER TABLE sources ADD COLUMN title TEXT NOT NULL DEFAULT ''"
            )

    def close(self) -> None:
        self._conn.close()

    def upsert_knowledge(
        self,
        source: KnowledgeSource,
        document: KnowledgeDocument,
        chunks: Sequence[KnowledgeChunk],
    ) -> None:
        try:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                """
                INSERT INTO knowledge_sources(
                    source_id, source_type, external_id, title, canonical_uri,
                    license, permission_status, visibility_scope, enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    source_type=excluded.source_type,
                    external_id=excluded.external_id,
                    title=excluded.title,
                    canonical_uri=excluded.canonical_uri,
                    license=excluded.license,
                    permission_status=excluded.permission_status,
                    visibility_scope=excluded.visibility_scope,
                    enabled=excluded.enabled
                """,
                (
                    source.source_id,
                    source.source_type,
                    source.external_id,
                    source.title,
                    source.canonical_uri,
                    source.license,
                    source.permission_status,
                    source.visibility_scope,
                    source.enabled,
                ),
            )
            existing = self._conn.execute(
                "SELECT version FROM knowledge_documents WHERE document_id=?",
                (document.document_id,),
            ).fetchone()
            version = existing["version"] if existing else self._conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM knowledge_documents WHERE source_id=? AND language=?
                """,
                (document.source_id, document.language),
            ).fetchone()[0]
            if document.active:
                self._conn.execute(
                    """
                    UPDATE knowledge_documents SET active=0
                    WHERE source_id=? AND language=? AND document_id!=?
                    """,
                    (document.source_id, document.language, document.document_id),
                )
            self._conn.execute(
                """
                INSERT INTO knowledge_documents(
                    document_id, source_id, language, content_hash,
                    canonical_path, version, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    language=excluded.language,
                    content_hash=excluded.content_hash,
                    canonical_path=excluded.canonical_path,
                    version=excluded.version,
                    active=excluded.active
                """,
                (
                    document.document_id,
                    document.source_id,
                    document.language,
                    document.content_hash,
                    document.canonical_path,
                    version,
                    document.active,
                ),
            )
            for chunk in chunks:
                self._conn.execute(
                    """
                    INSERT INTO knowledge_chunks(
                        chunk_id, document_id, ordinal, content, locator_kind,
                        start_seconds, end_seconds, page_start, page_end, path, heading
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        document_id=excluded.document_id,
                        ordinal=excluded.ordinal,
                        content=excluded.content,
                        locator_kind=excluded.locator_kind,
                        start_seconds=excluded.start_seconds,
                        end_seconds=excluded.end_seconds,
                        page_start=excluded.page_start,
                        page_end=excluded.page_end,
                        path=excluded.path,
                        heading=excluded.heading
                    """,
                    (
                        chunk.chunk_id,
                        chunk.document_id,
                        chunk.ordinal,
                        chunk.content,
                        chunk.locator_kind,
                        chunk.start_seconds,
                        chunk.end_seconds,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.path,
                        chunk.heading,
                    ),
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _project_v1(self) -> None:
        # ponytail: full refresh fits the pilot; use row upserts if write latency grows.
        self._conn.execute(
            """
            INSERT INTO knowledge_sources(
                source_id, source_type, external_id, title, canonical_uri,
                license, permission_status, visibility_scope, enabled
            )
            SELECT
                'youtube:' || video_id, 'youtube', video_id, title, url,
                'unknown', 'unknown', 'shared', 1
            FROM sources
            WHERE 1
            ON CONFLICT(source_id) DO UPDATE SET
                canonical_uri=excluded.canonical_uri,
                external_id=excluded.external_id,
                enabled=excluded.enabled
            """
        )
        self._conn.execute(
            """
            INSERT INTO knowledge_sources(
                source_id, source_type, external_id, title, canonical_uri,
                license, permission_status, visibility_scope, enabled
            )
            SELECT
                'youtube:' || video_id, 'youtube', video_id, '', MAX(url),
                'unknown', 'unknown', 'shared', 1
            FROM segments
            GROUP BY video_id
            ON CONFLICT(source_id) DO UPDATE SET
                canonical_uri=excluded.canonical_uri,
                external_id=excluded.external_id,
                enabled=excluded.enabled
            """
        )
        self._conn.execute(
            """
            INSERT INTO knowledge_documents(
                document_id, source_id, language, content_hash,
                canonical_path, version, active
            )
            SELECT
                'youtube:' || video_id || ':' || language || ':' || transcript_hash,
                'youtube:' || video_id, language, transcript_hash, '', 1, active
            FROM documents
            WHERE 1
            ON CONFLICT(document_id) DO UPDATE SET
                active=excluded.active,
                content_hash=excluded.content_hash
            """
        )
        self._conn.execute(
            """
            INSERT INTO knowledge_chunks(
                chunk_id, document_id, ordinal, content, locator_kind,
                start_seconds, end_seconds, page_start, page_end, path, heading
            )
            SELECT
                citation_id,
                'youtube:' || video_id || ':' || language || ':' || transcript_hash,
                ROW_NUMBER() OVER (
                    PARTITION BY video_id, language, transcript_hash
                    ORDER BY start_seconds, end_seconds, citation_id
                ) - 1,
                text, 'timestamp', start_seconds, end_seconds,
                NULL, NULL, NULL, NULL
            FROM segments
            WHERE 1
            ON CONFLICT(chunk_id) DO UPDATE SET
                document_id=excluded.document_id,
                ordinal=excluded.ordinal,
                content=excluded.content,
                start_seconds=excluded.start_seconds,
                end_seconds=excluded.end_seconds
            """
        )

    def load(self) -> dict[str, Any]:
        # Late import avoids cycle with founder_guide.__init__
        from . import Note, Segment

        sources = {
            row["video_id"]: Source(
                row["video_id"], row["url"], row["published_at"], row["title"]
            )
            for row in self._conn.execute("SELECT * FROM sources")
        }
        kinds: dict[tuple[str, str, str], str] = {}
        documents: dict[tuple[str, str, str], list[Any]] = {}
        active: dict[tuple[str, str], str] = {}
        urls: dict[str, str] = {
            video_id: source.url for video_id, source in sources.items()
        }

        for row in self._conn.execute("SELECT * FROM documents"):
            key = (row["video_id"], row["language"], row["transcript_hash"])
            kinds[key] = row["transcript_kind"]
            documents[key] = []
            if row["active"]:
                active[(row["video_id"], row["language"])] = row["transcript_hash"]

        for row in self._conn.execute(
            "SELECT * FROM segments ORDER BY video_id, language, transcript_hash, start_seconds"
        ):
            key = (row["video_id"], row["language"], row["transcript_hash"])
            documents.setdefault(key, []).append(
                Segment(
                    row["citation_id"],
                    row["video_id"],
                    row["language"],
                    row["url"],
                    row["start_seconds"],
                    row["end_seconds"],
                    row["text"],
                )
            )
            urls[row["video_id"]] = row["url"]

        notes = {
            row["note_id"]: Note(
                row["note_id"],
                row["video_id"],
                row["scope"],
                row["content"],
                row["stage"],
                row["url"],
            )
            for row in self._conn.execute("SELECT * FROM notes")
        }
        return {
            "sources": sources,
            "documents": {key: tuple(items) for key, items in documents.items()},
            "kinds": kinds,
            "active": active,
            "notes": notes,
            "urls": urls,
        }

    def upsert_source(self, source: Source) -> None:
        self._conn.execute(
            """
            INSERT INTO sources(video_id, url, published_at, title)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                url=excluded.url,
                published_at=excluded.published_at,
                title=excluded.title
            """,
            (source.video_id, source.url, source.published_at, source.title),
        )
        self._project_v1()
        self._conn.commit()

    def upsert_document(
        self,
        video_id: str,
        language: str,
        transcript_hash: str,
        transcript_kind: str,
        segments: tuple[Any, ...],
        active: bool,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO documents(video_id, language, transcript_hash, transcript_kind, active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(video_id, language, transcript_hash) DO UPDATE SET
                transcript_kind=excluded.transcript_kind,
                active=excluded.active
            """,
            (video_id, language, transcript_hash, transcript_kind, int(active)),
        )
        if active:
            self._conn.execute(
                """
                UPDATE documents SET active=0
                WHERE video_id=? AND language=? AND transcript_hash!=?
                """,
                (video_id, language, transcript_hash),
            )
        for segment in segments:
            self._conn.execute(
                """
                INSERT INTO segments(
                    citation_id, video_id, language, transcript_hash,
                    url, start_seconds, end_seconds, text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(citation_id) DO NOTHING
                """,
                (
                    segment.citation_id,
                    segment.video_id,
                    segment.language,
                    transcript_hash,
                    segment.url,
                    segment.start_seconds,
                    segment.end_seconds,
                    segment.text,
                ),
            )
        self._project_v1()
        self._conn.commit()

    def upsert_note(self, note: Any) -> None:
        self._conn.execute(
            """
            INSERT INTO notes(note_id, video_id, scope, content, stage, url)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(note_id) DO UPDATE SET
                content=excluded.content,
                stage=excluded.stage,
                url=excluded.url,
                scope=excluded.scope,
                video_id=excluded.video_id
            """,
            (
                note.note_id,
                note.video_id,
                note.scope,
                note.content,
                note.stage,
                note.url,
            ),
        )
        self._conn.commit()
