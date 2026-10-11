from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Citation:
    chunk_id: str
    source_id: str
    source_type: str
    title: str
    uri: str
    locator_kind: str
    start_seconds: int | None
    end_seconds: int | None
    page_start: int | None
    page_end: int | None
    path: str | None
    heading: str | None


@dataclass(frozen=True)
class SearchHit:
    content: str
    score: int
    citation: Citation


@dataclass(frozen=True)
class KnowledgeAnswer:
    text: str
    citations: tuple[Citation, ...]
    insufficient_evidence: bool


def search_knowledge(
    db_path: str | Path,
    query: str,
    *,
    scope: str,
    limit: int = 10,
) -> list[SearchHit]:
    terms = tuple(dict.fromkeys(re.findall(r"\w+", query.casefold())))
    if not terms or limit < 1:
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                c.*, s.source_id, s.source_type, s.title, s.canonical_uri
            FROM knowledge_chunks AS c
            JOIN knowledge_documents AS d ON d.document_id = c.document_id
            JOIN knowledge_sources AS s ON s.source_id = d.source_id
            WHERE d.active = 1
              AND s.enabled = 1
              AND s.visibility_scope IN ('shared', ?)
            """,
            (scope,),
        ).fetchall()
    finally:
        conn.close()

    hits = []
    for row in rows:
        content = row["content"]
        normalized = content.casefold()
        score = sum(normalized.count(term) for term in terms)
        if score:
            hits.append(
                SearchHit(
                    content=content,
                    score=score,
                    citation=Citation(
                        chunk_id=row["chunk_id"],
                        source_id=row["source_id"],
                        source_type=row["source_type"],
                        title=row["title"],
                        uri=row["canonical_uri"],
                        locator_kind=row["locator_kind"],
                        start_seconds=row["start_seconds"],
                        end_seconds=row["end_seconds"],
                        page_start=row["page_start"],
                        page_end=row["page_end"],
                        path=row["path"],
                        heading=row["heading"],
                    ),
                )
            )
    return sorted(
        hits,
        key=lambda hit: (-hit.score, hit.citation.source_id, hit.citation.chunk_id),
    )[:limit]


def answer_knowledge(
    db_path: str | Path,
    query: str,
    *,
    scope: str,
    limit: int = 10,
) -> KnowledgeAnswer:
    hits = search_knowledge(db_path, query, scope=scope, limit=limit)
    citations = tuple(hit.citation for hit in hits)
    if len(hits) < 2:
        return KnowledgeAnswer("", citations, True)
    return KnowledgeAnswer(
        " ".join(hit.content for hit in hits),
        citations,
        False,
    )


def hit_to_dict(hit: SearchHit) -> dict:
    return {
        "content": hit.content,
        "score": hit.score,
        "citation": asdict(hit.citation),
    }
