from __future__ import annotations

import hashlib
from pathlib import Path

from .models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource
from .store import SqliteStore
from .vault import list_books, load_book


def rebuild_index(vault_path: str | Path, db_path: str | Path) -> None:
    root = Path(vault_path).resolve()
    store = SqliteStore(db_path)
    try:
        for section, book_id in list_books(root):
            data = load_book(root, section, book_id)
            meta = data["meta"]
            full = data["full_path"].read_bytes()
            source_id = f"book:{book_id}"
            content_hash = hashlib.sha256(full).hexdigest()
            document_id = f"{source_id}:{content_hash}"
            canonical = f"{section}/{book_id}/full.md"
            store.upsert_knowledge(
                KnowledgeSource(
                    source_id=source_id,
                    source_type="book",
                    external_id=book_id,
                    title=meta.get("title", ""),
                    canonical_uri=canonical,
                    license=meta.get("license", "unknown"),
                    permission_status="unknown",
                    visibility_scope="shared",
                ),
                KnowledgeDocument(
                    document_id=document_id,
                    source_id=source_id,
                    language=meta.get("language", "es"),
                    content_hash=content_hash,
                    canonical_path=canonical,
                    active=1,
                ),
                [
                    KnowledgeChunk(
                        chunk_id=f"{document_id}:{ordinal}",
                        document_id=document_id,
                        ordinal=ordinal,
                        content=chunk["content"],
                        locator_kind="heading",
                        path=chunk["path"].relative_to(root).as_posix(),
                        heading=chunk["heading"],
                    )
                    for ordinal, chunk in enumerate(data["chunks"])
                ],
            )
    finally:
        store.close()
