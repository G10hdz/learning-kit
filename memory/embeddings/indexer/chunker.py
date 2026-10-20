"""Markdown text chunker for Obsidian vault files.

Splits markdown files into semantic chunks by heading boundaries,
with paragraph-level fallback. Strips YAML frontmatter and HTML comments.
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A single chunk of text with metadata."""

    text: str
    vault: str
    relative_path: str
    file_title: str
    heading: Optional[str]  # heading this chunk falls under (None for top)
    heading_level: int  # 0 = no heading, 1 = #, 2 = ##, etc.
    chunk_index: int  # position within the file
    modified_at: str  # ISO 8601
    word_count: int
    sha256: str  # SHA256 of the source file


def compute_file_hash(filepath: str) -> str:
    """Compute SHA-256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


YAML_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
DATAVIEW_BLOCK_RE = re.compile(r"```dataview.*?```", re.DOTALL)


def strip_frontmatter(text: str) -> tuple[str, dict]:
    """Strip YAML frontmatter and return (content, metadata dict).

    Extracts basic metadata like 'title' and 'tags' from frontmatter.
    """
    metadata: dict = {}
    match = YAML_FRONTMATTER_RE.match(text)
    if match:
        front_block = match.group(0)
        # Simple key: value extraction (no full YAML parser needed)
        for line in front_block.strip().split("\n")[1:-1]:  # skip --- markers
            if ":" in line:
                key, _, val = line.partition(":")
                metadata[key.strip()] = val.strip().strip('"').strip("'")
        text = text[match.end():]
    return text, metadata


def strip_html_comments(text: str) -> str:
    """Remove HTML comments from text."""
    return HTML_COMMENT_RE.sub("", text)


def strip_dataview_blocks(text: str) -> str:
    """Remove dataview code blocks (not useful for search)."""
    return DATAVIEW_BLOCK_RE.sub("", text)


def normalize_wikilinks(text: str) -> str:
    """Convert [[Page|alias]] wikilinks to their display text."""
    def _replace(match):
        inner = match.group(1)
        if "|" in inner:
            return inner.split("|", 1)[1]
        return inner
    return WIKILINK_RE.sub(_replace, text)


def compute_title(filepath: str, frontmatter: dict) -> str:
    """Determine title from frontmatter or filename."""
    title = frontmatter.get("title", "")
    if title:
        return title
    # Fall back to filename without extension
    name = Path(filepath).stem
    return name.replace("-", " ").replace("_", " ").title()


def get_modified_at(filepath: str) -> str:
    """Get file modification time as ISO 8601 string."""
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.fromtimestamp(mtime).isoformat()
    except OSError:
        return datetime.now().isoformat()


class TextChunker:
    """Split markdown files into chunks for embedding.

    Default strategy: split by ## headings. Falls back to paragraph
    splitting if no headings are found.
    """

    def __init__(
        self,
        chunk_by: str = "heading",
        heading_level: int = 2,
        max_paragraph_words: int = 300,
        min_chunk_words: int = 10,
        max_chars: int = 16000,
    ):
        self.chunk_by = chunk_by
        self.heading_level = heading_level
        self.max_paragraph_words = max_paragraph_words
        self.min_chunk_words = min_chunk_words
        # Hard character cap per chunk: guarantees every chunk stays under the
        # embedding model's token limit (prevents oversized-input failures on
        # providers like OpenRouter/text-embedding-3-large).
        self.max_chars = max_chars

    def chunk_file(
        self,
        filepath: str,
        vault_name: str,
        relative_path: str,
    ) -> list[Chunk]:
        """Chunk a markdown file into a list of Chunks.

        Args:
            filepath: Absolute path to the .md file.
            vault_name: Name of the vault (e.g. "MyVault").
            relative_path: Path relative to vault root.

        Returns:
            List of Chunk objects.
        """
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                raw_text = f.read()
        except (OSError, PermissionError) as e:
            logger.error("Cannot read %s: %s", filepath, e)
            return []

        # Compute hash
        file_hash = compute_file_hash(filepath)
        modified_at = get_modified_at(filepath)

        # Clean text
        text, frontmatter = strip_frontmatter(raw_text)
        text = strip_html_comments(text)
        text = strip_dataview_blocks(text)
        text = normalize_wikilinks(text)
        file_title = compute_title(filepath, frontmatter)

        # Chunk
        if self.chunk_by == "heading" or self.chunk_by == "auto":
            chunks = self._chunk_by_headings(text, file_title)
            if not chunks:
                # No headings found, fall back to paragraphs
                chunks = self._chunk_by_paragraphs(text, file_title)
        else:
            chunks = self._chunk_by_paragraphs(text, file_title)

        # Enforce the hard character cap (guards against oversized chunks that
        # would exceed an embedding model's token limit).
        chunks = self._enforce_max_chars(chunks)

        # Build Chunk objects
        result = []
        for i, (heading, heading_level, content) in enumerate(chunks):
            # Skip near-empty chunks
            words = content.split()
            if len(words) < self.min_chunk_words:
                continue

            result.append(
                Chunk(
                    text=content.strip(),
                    vault=vault_name,
                    relative_path=relative_path,
                    file_title=file_title,
                    heading=heading,
                    heading_level=heading_level,
                    chunk_index=i,
                    modified_at=modified_at,
                    word_count=len(words),
                    sha256=file_hash,
                )
            )

        return result

    def _chunk_by_headings(
        self, text: str, file_title: str
    ) -> list[tuple[Optional[str], int, str]]:
        """Split text by headings at the configured level or below.

        Returns list of (heading_text, heading_level, content) tuples.
        """
        lines = text.split("\n")
        chunks: list[tuple[Optional[str], int, str]] = []
        current_heading: Optional[str] = None
        current_heading_level: int = 0
        current_lines: list[str] = []
        min_level = self.heading_level  # e.g. 2 for ##

        for line in lines:
            heading_match = HEADING_RE.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                # Save previous chunk
                if current_lines:
                    content = "\n".join(current_lines).strip()
                    if content:
                        chunks.append(
                            (current_heading, current_heading_level, content)
                        )
                # Start new chunk
                if level >= min_level:
                    current_heading = heading_match.group(2).strip()
                    current_heading_level = level
                    current_lines = []
                else:
                    # Higher-level heading (#): treat as part of current chunk
                    current_lines.append(line)
            else:
                current_lines.append(line)

        # Last chunk
        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                chunks.append((current_heading, current_heading_level, content))

        # If no chunks were created, treat whole file as one chunk
        if not chunks and text.strip():
            chunks.append((None, 0, text.strip()))

        return chunks

    def _enforce_max_chars(
        self, chunks: list[tuple[Optional[str], int, str]]
    ) -> list[tuple[Optional[str], int, str]]:
        """Hard-split any chunk whose text exceeds ``max_chars``.

        Keeps the same heading/level metadata for each sub-piece so retrieval
        context is preserved. Splits on paragraph boundaries where possible,
        otherwise on character count.
        """
        out: list[tuple[Optional[str], int, str]] = []
        for heading, level, content in chunks:
            if len(content) <= self.max_chars:
                out.append((heading, level, content))
                continue

            # Try to split on paragraph boundaries first.
            pieces = content.split("\n\n")
            buffer = ""
            for piece in pieces:
                if not buffer:
                    buffer = piece
                elif len(buffer) + len(piece) + 2 <= self.max_chars:
                    buffer += "\n\n" + piece
                else:
                    out.append((heading, level, buffer.strip()))
                    buffer = piece
            if buffer:
                out.append((heading, level, buffer.strip()))

            # If a single paragraph still exceeds the cap, hard-split by chars.
            final: list[tuple[Optional[str], int, str]] = []
            for h, lvl, c in out[-len(pieces):] if pieces else []:
                if len(c) <= self.max_chars:
                    final.append((h, lvl, c))
                else:
                    for j in range(0, len(c), self.max_chars):
                        final.append((h, lvl, c[j : j + self.max_chars]))
            if final:
                out = out[: -max(len(pieces), 1)] + final
        return out

    def _chunk_by_paragraphs(
        self, text: str, file_title: str
    ) -> list[tuple[Optional[str], int, str]]:
        """Split text by paragraphs (double newlines).

        Merges consecutive small paragraphs to avoid tiny chunks.
        """
        paragraphs = re.split(r"\n\s*\n", text.strip())
        merged: list[str] = []
        buffer = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            word_count = len(para.split())

            if word_count < self.min_chunk_words and buffer:
                # Attach to previous buffer
                buffer += "\n\n" + para
            elif word_count > self.max_paragraph_words and not buffer:
                # Very long paragraph: treat it as its own chunk
                # Then sub-split by sentences for safety
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sub_chunks = []
                current = ""
                for sent in sentences:
                    if len(current.split()) + len(sent.split()) > self.max_paragraph_words:
                        sub_chunks.append(current)
                        current = sent
                    else:
                        current = (current + " " + sent).strip()
                if current:
                    sub_chunks.append(current)

                if buffer:
                    merged.append(buffer)
                    buffer = ""
                merged.extend(sub_chunks)
            else:
                if buffer:
                    buffer += "\n\n" + para
                else:
                    buffer = para

                if len(buffer.split()) >= self.max_paragraph_words:
                    merged.append(buffer)
                    buffer = ""

        if buffer:
            merged.append(buffer)

        return [(None, 0, p) for p in merged if p.strip()]


def chunk_id(chunk: Chunk) -> str:
    """Generate a deterministic unique ID for a chunk.

    Same content + same path + same position = same ID.
    This ensures idempotent upserts.
    """
    raw = f"{chunk.text}::{chunk.relative_path}::{chunk.chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
