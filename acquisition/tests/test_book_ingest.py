import tempfile
import unittest
from pathlib import Path

from founder_guide.book import ingest_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "sample_book.md"


class BookIngestTests(unittest.TestCase):
    metadata = {
        "book_id": "mom-test",
        "section": "01-startup-negocio",
        "title": "The Mom Test",
        "author": "Rob Fitzpatrick",
        "license": "team-notes",
    }

    def test_spec_007_markdown_ingest_writes_meta_full_and_chunk(self) -> None:
        source = FIXTURE.read_text()
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            ingest_markdown(FIXTURE, vault, **self.metadata)

            book_dir = vault / "01-startup-negocio" / "mom-test"
            metadata = (book_dir / "_meta.yaml").read_text()
            self.assertFalse(metadata.startswith("---"))
            self.assertTrue((book_dir / "full.md").is_file())
            self.assertEqual((book_dir / "full.md").read_text(), source)

            chunks = sorted((book_dir / "chunks").glob("*.md"))
            self.assertGreaterEqual(len(chunks), 1)

            chunk = chunks[0].read_text()
            self.assertIn("source_type: book", chunk)
            self.assertIn('book_id: "mom-test"', chunk)
            self.assertIn('section: "01-startup-negocio"', chunk)
            self.assertIn('title: "The Mom Test"', chunk)
            self.assertIn('license: "team-notes"', chunk)

    def test_spec_008_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            metadata = {**self.metadata, "section": "../escape"}

            with self.assertRaises(ValueError):
                ingest_markdown(FIXTURE, vault, **metadata)

            self.assertFalse((root / "escape").exists())

    def test_spec_009_reingest_same_content_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            self.assertTrue(ingest_markdown(FIXTURE, vault, **self.metadata))

            book_dir = vault / "01-startup-negocio" / "mom-test"
            before = {
                path.relative_to(book_dir): path.stat().st_mtime_ns
                for path in book_dir.rglob("*")
                if path.is_file()
            }
            self.assertFalse(ingest_markdown(FIXTURE, vault, **self.metadata))
            after = {
                path.relative_to(book_dir): path.stat().st_mtime_ns
                for path in book_dir.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
