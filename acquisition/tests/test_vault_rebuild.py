import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from founder_guide.book import ingest_markdown
from founder_guide.index import rebuild_index

FIXTURE = Path(__file__).parent / "fixtures" / "sample_book.md"

METADATA = {
    "book_id": "mom-test",
    "section": "01-startup-negocio",
    "title": "The Mom Test",
    "author": "Rob Fitzpatrick",
    "license": "team-notes",
}


def _rows(db_path: Path) -> dict[str, tuple]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    source = conn.execute("SELECT * FROM knowledge_sources").fetchone()
    document = conn.execute("SELECT * FROM knowledge_documents").fetchone()
    chunk = conn.execute("SELECT * FROM knowledge_chunks").fetchone()
    conn.close()
    return {"source": source, "document": document, "chunk": chunk}


class VaultRebuildTests(unittest.TestCase):
    def test_spec_013_rebuild_index_writes_v2_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            db_path = root / "store.db"
            ingest_markdown(FIXTURE, vault, **METADATA)

            rebuild_index(vault, db_path)

            rows = _rows(db_path)
            source, document, chunk = (
                rows["source"],
                rows["document"],
                rows["chunk"],
            )

            self.assertEqual(source["source_id"], "book:mom-test")
            self.assertEqual(source["source_type"], "book")
            self.assertEqual(source["license"], "team-notes")
            self.assertEqual(
                source["canonical_uri"],
                "01-startup-negocio/mom-test/full.md",
            )
            self.assertEqual(source["enabled"], 1)

            self.assertEqual(document["source_id"], "book:mom-test")
            self.assertEqual(document["active"], 1)
            self.assertEqual(document["version"], 1)
            content_hash = hashlib.sha256(
                (vault / "01-startup-negocio" / "mom-test" / "full.md")
                .read_bytes()
            ).hexdigest()
            self.assertEqual(document["content_hash"], content_hash)
            self.assertEqual(
                document["document_id"], f"book:mom-test:{content_hash}"
            )
            self.assertEqual(document["language"], "es")
            self.assertEqual(
                document["canonical_path"],
                "01-startup-negocio/mom-test/full.md",
            )

            chunk_file = (
                vault / "01-startup-negocio" / "mom-test" / "chunks" / "001.md"
            )
            expected_content = chunk_file.read_bytes().partition(b"---\n\n")[2]
            self.assertEqual(chunk["document_id"], document["document_id"])
            self.assertEqual(chunk["content"], expected_content.decode())
            self.assertEqual(chunk["locator_kind"], "heading")
            self.assertEqual(
                chunk["path"], "01-startup-negocio/mom-test/chunks/001.md"
            )

    def test_spec_014_rebuild_is_deterministic_across_empty_dbs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            vault_a = root / "vault-a"
            db_a = root / "store-a.db"
            ingest_markdown(FIXTURE, vault_a, **METADATA)
            rebuild_index(vault_a, db_a)

            vault_b = root / "vault-b"
            db_b = root / "store-b.db"
            ingest_markdown(FIXTURE, vault_b, **METADATA)
            rebuild_index(vault_b, db_b)

            ids_a = _rows(db_a)
            ids_b = _rows(db_b)
            self.assertEqual(
                ids_a["source"]["source_id"], ids_b["source"]["source_id"]
            )
            self.assertEqual(
                ids_a["document"]["document_id"],
                ids_b["document"]["document_id"],
            )
            self.assertEqual(
                ids_a["chunk"]["chunk_id"], ids_b["chunk"]["chunk_id"]
            )

    def test_spec_015_rebuild_keeps_only_latest_document_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "book.md"
            vault = root / "vault"
            db_path = root / "store.db"

            source.write_text("# Primera version\n\nContenido inicial.\n")
            ingest_markdown(source, vault, **METADATA)
            rebuild_index(vault, db_path)

            source.write_text("# Segunda version\n\nContenido corregido.\n")
            ingest_markdown(source, vault, **METADATA)
            rebuild_index(vault, db_path)

            conn = sqlite3.connect(db_path)
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM knowledge_documents"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM knowledge_documents WHERE active=1"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT version, active FROM knowledge_documents ORDER BY version"
                ).fetchall(),
                [(1, 0), (2, 1)],
            )
            conn.close()

    def test_spec_016_rebuild_ignores_internal_vault_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            db_path = root / "store.db"
            ingest_markdown(FIXTURE, vault, **METADATA)
            ingest_markdown(
                FIXTURE,
                vault,
                **{
                    **METADATA,
                    "book_id": "private-copy",
                    "section": "_raw",
                    "license": "private",
                },
            )

            rebuild_index(vault, db_path)

            conn = sqlite3.connect(db_path)
            self.assertEqual(
                conn.execute(
                    "SELECT source_id FROM knowledge_sources ORDER BY source_id"
                ).fetchall(),
                [("book:mom-test",)],
            )
            conn.close()


if __name__ == "__main__":
    unittest.main()
