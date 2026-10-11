from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_book(
    vault_path: str | Path,
    section: str,
    book_id: str,
    metadata: dict[str, Any],
    raw: bytes,
    chunks: list[bytes],
) -> bool:
    book_dir = _book_dir(vault_path, section, book_id)
    yaml = _yaml(metadata).encode()
    frontmatter = b"---\n" + yaml + b"---"
    files = {
        book_dir / "_meta.yaml": yaml,
        book_dir / "full.md": raw,
        **{
            book_dir / "chunks" / f"{index:03d}.md": frontmatter + b"\n\n" + chunk
            for index, chunk in enumerate(chunks, start=1)
        },
    }
    if all(path.is_file() and path.read_bytes() == content for path, content in files.items()):
        return False

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return True


def _book_dir(vault_path: str | Path, section: str, book_id: str) -> Path:
    if not book_id or Path(book_id).name != book_id or book_id in {".", ".."}:
        raise ValueError("book_id must be one path segment")
    root = Path(vault_path).resolve()
    book_dir = (root / section / book_id).resolve()
    if not section or not book_dir.is_relative_to(root):
        raise ValueError("section must stay inside the vault")
    return book_dir


def _yaml(metadata: dict[str, Any]) -> str:
    lines = []
    for key, value in metadata.items():
        rendered = value if key == "source_type" else json.dumps(value, ensure_ascii=False)
        lines.append(f"{key}: {rendered}")
    return "\n".join(lines) + "\n"


def list_books(vault_path: str | Path) -> list[tuple[str, str]]:
    root = Path(vault_path).resolve()
    books = []
    for section in sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    ):
        for book_dir in sorted(path for path in section.iterdir() if path.is_dir()):
            if (book_dir / "_meta.yaml").is_file():
                books.append((section.name, book_dir.name))
    return books


def load_book(
    vault_path: str | Path,
    section: str,
    book_id: str,
) -> dict[str, Any]:
    book_dir = _book_dir(vault_path, section, book_id)
    chunks = []
    for chunk_path in sorted(book_dir.joinpath("chunks").glob("*.md")):
        content = chunk_path.read_bytes().partition(b"---\n\n")[2].decode()
        chunks.append(
            {"path": chunk_path, "content": content, "heading": _first_heading(content)}
        )
    return {
        "meta": _load_meta(book_dir / "_meta.yaml"),
        "full_path": book_dir / "full.md",
        "chunks": chunks,
    }


def _load_meta(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        meta[key.strip()] = str(parsed)
    return meta


def _first_heading(content: str) -> str | None:
    for line in content.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None
