import sqlite3
import tempfile
import unittest
from pathlib import Path

from founder_guide.book import ingest_markdown
from founder_guide.index import rebuild_index
from founder_guide.query import answer_knowledge, search_knowledge


FIXTURE = Path(__file__).parent / "fixtures" / "sample_book.md"
METADATA = {
    "book_id": "mom-test",
    "section": "01-startup-negocio",
    "title": "The Mom Test",
    "author": "Rob Fitzpatrick",
    "license": "team-notes",
}


def _seed_two_books(vault: Path, db_path: Path) -> None:
    ingest_markdown(FIXTURE, vault, **METADATA)
    second = vault / "other.md"
    second.write_text(
        "# Otro\n\nHabla con usuarios reales en el mercado.\n\n"
        "## Mas\n\nValidar con demos cortas ante usuarios.\n"
    )
    ingest_markdown(
        second,
        vault,
        book_id="other-book",
        section="01-startup-negocio",
        title="Other",
        author="Anon",
        license="team-notes",
    )
    rebuild_index(vault, db_path)


class KnowledgeSearchTests(unittest.TestCase):
    def test_spec_017_search_returns_source_backed_citation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            db_path = root / "store.db"
            ingest_markdown(FIXTURE, vault, **METADATA)
            rebuild_index(vault, db_path)

            hits = search_knowledge(db_path, "usuarios reales", scope="positronica")

            self.assertEqual(len(hits), 1)
            hit = hits[0]
            self.assertIn("usuarios reales", hit.content)
            self.assertEqual(hit.citation.source_id, "book:mom-test")
            self.assertEqual(hit.citation.source_type, "book")
            self.assertEqual(hit.citation.title, "The Mom Test")
            self.assertEqual(
                hit.citation.uri,
                "01-startup-negocio/mom-test/full.md",
            )
            self.assertEqual(hit.citation.locator_kind, "heading")
            self.assertEqual(
                hit.citation.path,
                "01-startup-negocio/mom-test/chunks/001.md",
            )
            self.assertEqual(hit.citation.heading, "Capitulo Uno")

    def test_spec_018_search_enforces_visibility_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            db_path = root / "store.db"
            ingest_markdown(FIXTURE, vault, **METADATA)
            rebuild_index(vault, db_path)
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE knowledge_sources SET visibility_scope='positronica'"
            )
            conn.commit()
            conn.close()

            self.assertEqual(
                search_knowledge(db_path, "usuarios", scope="mpc"),
                [],
            )
            self.assertEqual(
                len(search_knowledge(db_path, "usuarios", scope="positronica")),
                1,
            )

    def test_spec_019_empty_or_missing_query_returns_no_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "store.db"
            vault = Path(directory) / "empty-vault"
            vault.mkdir()
            rebuild_index(vault, db_path)

            self.assertEqual(search_knowledge(db_path, "", scope="shared"), [])
            self.assertEqual(
                search_knowledge(db_path, "inexistente", scope="shared"),
                [],
            )

    def test_answer_knowledge_insufficient_with_one_hit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            db_path = root / "store.db"
            ingest_markdown(FIXTURE, vault, **METADATA)
            rebuild_index(vault, db_path)

            answer = answer_knowledge(
                db_path, "usuarios reales", scope="shared"
            )
            self.assertTrue(answer.insufficient_evidence)
            self.assertEqual(answer.text, "")
            self.assertEqual(len(answer.citations), 1)

    def test_answer_knowledge_extractive_with_two_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            db_path = root / "store.db"
            _seed_two_books(vault, db_path)

            answer = answer_knowledge(db_path, "usuarios", scope="shared")
            self.assertFalse(answer.insufficient_evidence)
            self.assertIn("usuarios", answer.text.casefold())
            self.assertGreaterEqual(len(answer.citations), 2)
            self.assertTrue(
                all(c.source_type == "book" for c in answer.citations)
            )


if __name__ == "__main__":
    unittest.main()
