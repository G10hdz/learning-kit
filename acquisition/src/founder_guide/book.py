from __future__ import annotations

import re
from pathlib import Path

from .vault import write_book


def ingest_file(
    source_path: str | Path,
    vault_path: str | Path,
    *,
    book_id: str,
    section: str,
    title: str,
    author: str,
    license: str,
    language: str = "es",
) -> bool:
    source = Path(source_path)
    ext = source.suffix.lower()
    if ext == ".pdf":
        raw = extract_pdf(source)
    elif ext == ".epub":
        raw = extract_epub(source)
    elif ext in (".md", ".txt"):
        raw = source.read_bytes()
    else:
        raise ValueError(f"formato no soportado: {ext}")

    metadata = {
        "source_type": "book",
        "book_id": book_id,
        "section": section,
        "title": title,
        "author": author,
        "license": license,
        "language": language,
        "source": source.name,
    }
    chunks = chunk_text(raw.decode("utf-8", errors="replace"))
    return write_book(
        vault_path,
        section,
        book_id,
        metadata,
        raw,
        [c.encode("utf-8") for c in chunks],
    )


def ingest_markdown(
    source_path: str | Path,
    vault_path: str | Path,
    *,
    book_id: str,
    section: str,
    title: str,
    author: str,
    license: str,
    language: str = "es",
) -> bool:
    return ingest_file(
        source_path,
        vault_path,
        book_id=book_id,
        section=section,
        title=title,
        author=author,
        license=license,
        language=language,
    )


def extract_pdf(path: Path) -> bytes:
    import fitz

    doc = fitz.open(str(path))
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    text = "\n\n".join(parts)
    return text.encode("utf-8")


def extract_epub(path: Path) -> bytes:
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        import html

        raw_html = item.get_content().decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts).encode("utf-8")


def chunk_text(text: str, target_tokens: int = 1000, overlap: int = 100) -> list[str]:
    """Chunk por ~1000 tokens (estimado: 1 token ~ 4 chars) con overlap."""
    target_chars = target_tokens * 4
    overlap_chars = overlap * 4
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        plen = len(para)
        if current_len + plen > target_chars and current:
            chunk = "\n\n".join(current)
            chunks.append(chunk)
            # overlap: mantener ultimo parrafo si no es muy grande
            if overlap_chars > 0 and len(current[-1]) < overlap_chars:
                current = [current[-1]]
                current_len = len(current[-1])
            else:
                current = []
                current_len = 0
        current.append(para)
        current_len += plen

    if current:
        chunks.append("\n\n".join(current))

    return chunks if chunks else [text]


def chunk_markdown(raw: bytes) -> list[bytes]:
    return [raw]
