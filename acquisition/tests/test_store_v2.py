import sqlite3
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from founder_guide.catalog import Source
from founder_guide.store import SqliteStore

V1_SCHEMA = """
CREATE TABLE sources (
    video_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    published_at TEXT NOT NULL
);
CREATE TABLE documents (
    video_id TEXT NOT NULL,
    language TEXT NOT NULL,
    transcript_hash TEXT NOT NULL,
    transcript_kind TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (video_id, language, transcript_hash)
);
CREATE TABLE segments (
    citation_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    language TEXT NOT NULL,
    transcript_hash TEXT NOT NULL,
    url TEXT NOT NULL,
    start_seconds INTEGER NOT NULL,
    end_seconds INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE notes (
    note_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    stage TEXT NOT NULL,
    url TEXT NOT NULL
);
"""

URL = "https://www.youtube.com/watch?v=video-1"


@dataclass(frozen=True)
class Segment:
    citation_id: str
    video_id: str
    language: str
    url: str
    start_seconds: int
    end_seconds: int
    text: str


def build_v1_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(V1_SCHEMA)
    conn.execute(
        "INSERT INTO sources(video_id, url, published_at) VALUES (?, ?, ?)",
        ("video-1", URL, "2026-01-01"),
    )
    conn.execute(
        "INSERT INTO documents(video_id, language, transcript_hash, transcript_kind, active) "
        "VALUES (?, ?, ?, ?, ?)",
        ("video-1", "es", "hash-1", "manual", 1),
    )
    conn.execute(
        "INSERT INTO segments("
        "citation_id, video_id, language, transcript_hash, url, start_seconds, end_seconds, text"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("youtube:video-1:es:hash-1:0", "video-1", "es", "hash-1", URL, 42, 57, "Hola mundo"),
    )
    conn.commit()
    conn.close()


class SqliteV2MigrationTests(unittest.TestCase):
    def test_spec_010_open_migrates_v1_tables_and_projects_v2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "store.db"
            build_v1_db(db_path)

            store = SqliteStore(db_path)
            store.close()

            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self.assertEqual(
                conn.execute("PRAGMA user_version").fetchone()[0], 2
            )

            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            for name in (
                "sources",
                "documents",
                "segments",
                "notes",
                "knowledge_sources",
                "knowledge_documents",
                "knowledge_chunks",
            ):
                self.assertIn(name, tables)

            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0], 1
            )

            source = conn.execute("SELECT * FROM knowledge_sources").fetchone()
            self.assertEqual(source["source_id"], "youtube:video-1")
            self.assertEqual(source["source_type"], "youtube")
            self.assertEqual(source["external_id"], "video-1")
            self.assertEqual(source["canonical_uri"], URL)
            self.assertEqual(source["visibility_scope"], "shared")

            document = conn.execute("SELECT * FROM knowledge_documents").fetchone()
            self.assertEqual(document["document_id"], "youtube:video-1:es:hash-1")
            self.assertEqual(document["content_hash"], "hash-1")
            self.assertEqual(document["active"], 1)

            chunk = conn.execute("SELECT * FROM knowledge_chunks").fetchone()
            self.assertEqual(chunk["chunk_id"], "youtube:video-1:es:hash-1:0")
            self.assertEqual(chunk["locator_kind"], "timestamp")
            self.assertEqual(chunk["start_seconds"], 42)
            self.assertEqual(chunk["end_seconds"], 57)
            conn.close()

    def test_spec_010_reopen_does_not_duplicate_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "store.db"
            build_v1_db(db_path)

            SqliteStore(db_path).close()
            SqliteStore(db_path).close()

            conn = sqlite3.connect(db_path)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM knowledge_sources").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()[0], 1
            )
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM knowledge_chunks").fetchone()[0], 1
            )
            conn.close()

    def test_spec_011_write_through_updates_v2_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "store.db"
            store = SqliteStore(db_path)
            store.upsert_source(Source("video-1", URL, "2026-01-01"))
            store.upsert_document(
                "video-1",
                "es",
                "hash-1",
                "manual",
                (
                    Segment(
                        "youtube:video-1:es:hash-1:0",
                        "video-1",
                        "es",
                        URL,
                        42,
                        57,
                        "Hola mundo",
                    ),
                ),
                True,
            )

            conn = sqlite3.connect(db_path)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM knowledge_sources"
            ).fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM knowledge_documents"
            ).fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM knowledge_chunks"
            ).fetchone()[0], 1)
            conn.close()
            store.close()

    def test_spec_012_document_write_projects_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "store.db"
            store = SqliteStore(db_path)
            store.upsert_document(
                "video-1",
                "es",
                "hash-1",
                "manual",
                (
                    Segment(
                        "youtube:video-1:es:hash-1:0",
                        "video-1",
                        "es",
                        URL,
                        42,
                        57,
                        "Hola mundo",
                    ),
                ),
                True,
            )

            conn = sqlite3.connect(db_path)
            self.assertEqual(
                conn.execute(
                    "SELECT source_id, canonical_uri FROM knowledge_sources"
                ).fetchone(),
                ("youtube:video-1", URL),
            )
            conn.close()
            store.close()


if __name__ == "__main__":
    unittest.main()
