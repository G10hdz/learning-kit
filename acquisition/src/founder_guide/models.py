from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeSource:
    source_id: str
    source_type: str
    external_id: str
    title: str
    canonical_uri: str
    license: str
    permission_status: str
    visibility_scope: str
    enabled: int = 1


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    source_id: str
    language: str
    content_hash: str
    canonical_path: str
    version: int = 1
    active: int = 0


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    document_id: str
    ordinal: int
    content: str
    locator_kind: str
    start_seconds: int | None = None
    end_seconds: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    path: str | None = None
    heading: str | None = None
