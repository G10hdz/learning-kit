"""Search engine — embed queries and search ChromaDB."""

import logging
from dataclasses import dataclass
from typing import Optional

from providers.base import BaseEmbeddingProvider
from store.chroma_store import ChromaStore

logger = logging.getLogger(__name__)

# Cosine distance → similarity score conversion
# ChromaDB uses cosine distance (0 = identical, 1 = orthogonal, 2 = opposite)
# We convert to a 0-1 similarity score.
_MAX_COSINE_DISTANCE = 1.0


def _to_similarity(distance: float) -> float:
    """Convert ChromaDB cosine distance to a 0-1 similarity score."""
    # Clamp to [0, 1] range
    score = 1.0 - min(max(distance, 0.0), _MAX_COSINE_DISTANCE)
    return round(score, 4)


@dataclass
class SearchResult:
    """A single search result with metadata."""

    text: str
    vault: str
    relative_path: str
    file_title: str
    heading: str
    score: float  # 0.0 to 1.0 similarity
    word_count: int
    modified_at: str


class SearchEngine:
    """Embed queries and search the ChromaDB collection."""

    def __init__(
        self,
        provider: BaseEmbeddingProvider,
        chroma_store: ChromaStore,
    ):
        self.provider = provider
        self.chroma_store = chroma_store

    def search(
        self,
        query: str,
        n_results: int = 10,
        vault: Optional[str] = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Search across all indexed vaults.

        Args:
            query: Natural language search query.
            n_results: Maximum number of results to return.
            vault: Optional vault name filter.
            min_score: Minimum similarity score (0.0 to 1.0).

        Returns:
            List of SearchResult objects, sorted by score (descending).
        """
        if not query.strip():
            return []

        # Embed query
        query_embedding = self.provider.embed([query])[0]

        # Build filter
        where = None
        if vault:
            where = {"vault": vault}

        # Search
        raw_results = self.chroma_store.search(
            query_embedding=query_embedding,
            n_results=n_results,
            where=where,
        )

        # Format
        results = []
        for r in raw_results:
            score = _to_similarity(r.get("distance", 1.0))
            if score < min_score:
                continue
            meta = r.get("metadata", {})
            results.append(
                SearchResult(
                    text=r.get("document", ""),
                    vault=meta.get("vault", ""),
                    relative_path=meta.get("relative_path", ""),
                    file_title=meta.get("file_title", ""),
                    heading=meta.get("heading", ""),
                    score=score,
                    word_count=meta.get("word_count", 0),
                    modified_at=meta.get("modified_at", ""),
                )
            )

        return results

    def format_results(
        self,
        results: list[SearchResult],
        show_text: bool = True,
        max_text_chars: int = 300,
    ) -> str:
        """Format search results as a readable string for CLI output.

        Args:
            results: List of SearchResult objects.
            show_text: Whether to include chunk text.
            max_text_chars: Max characters of text to show per result.

        Returns:
            Formatted string.
        """
        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] Score: {r.score:.4f}")

            location_parts = [r.vault]
            if r.relative_path:
                location_parts.append(r.relative_path)
            lines.append(f"    Location: {'/'.join(location_parts)}")

            if r.file_title:
                lines.append(f"    Title: {r.file_title}")
            if r.heading:
                lines.append(f"    Section: {r.heading}")
            if r.word_count:
                lines.append(f"    Words: {r.word_count}")

            if show_text and r.text:
                text = r.text[:max_text_chars]
                if len(r.text) > max_text_chars:
                    text += "..."
                lines.append(f"    ──\n    {text}")

            lines.append("")  # blank line between results

        return "\n".join(lines)
