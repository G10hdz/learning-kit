#!/usr/bin/env python3
"""
Obsidian Vault Semantic Indexing — CLI Entry Point

Usage:
    python index_vaults.py --full                                Full rebuild
    python index_vaults.py --update                              Incremental update
    python index_vaults.py --search "query"                      Semantic search
    python index_vaults.py --search                              Interactive search
    python index_vaults.py --provider openrouter --full          Use OpenRouter
    python index_vaults.py --vault MyVault --search "love"
"""

import argparse
import logging
import sys
import time

from config import Config
from providers import get_provider
from providers.base import BaseEmbeddingProvider
from store.chroma_store import ChromaStore
from indexer.chunker import TextChunker
from indexer.vault_indexer import VaultIndexer
from search.search_engine import SearchEngine, SearchResult

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO"):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt="%H:%M:%S",
    )
    # Quiet down chatty libs
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Provider initialization
# ---------------------------------------------------------------------------

def init_provider(args) -> BaseEmbeddingProvider:
    """Initialize the embedding provider based on CLI args or config."""
    provider_name = args.provider or Config.EMBEDDING_PROVIDER

    return get_provider(
        name=provider_name,
        ollama_endpoint=Config.OLLAMA_ENDPOINT,
        ollama_model=Config.OLLAMA_MODEL,
        ollama_timeout=Config.OLLAMA_TIMEOUT,
        openrouter_api_key=Config.OPENROUTER_API_KEY,
        openrouter_base_url=Config.OPENROUTER_BASE_URL,
        openrouter_model=Config.OPENROUTER_MODEL,
        openrouter_timeout=Config.OPENROUTER_TIMEOUT,
    )


def _make_chunker() -> TextChunker:
    """Build a TextChunker from the current config."""
    return TextChunker(
        chunk_by=Config.CHUNK_BY,
        heading_level=Config.CHUNK_HEADING_LEVEL,
        max_paragraph_words=Config.CHUNK_PARAGRAPH_MAX_WORDS,
        max_chars=Config.CHUNK_MAX_CHARS,
    )


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def cmd_full(provider, chroma_store, vaults):
    """Full rebuild of all vaults."""
    chunker = _make_chunker()
    indexer = VaultIndexer(
        vault_paths=vaults,
        provider=provider,
        chroma_store=chroma_store,
        chunker=chunker,
        hash_cache_path=Config.HASH_CACHE_PATH,
    )

    t0 = time.time()
    stats = indexer.index_full()
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f" Full Index Complete ({elapsed:.1f}s)")
    print(f"{'='*60}")
    print(f"  Provider:       {provider.name}")
    print(f"  Files indexed:  {stats['files_indexed']}")
    print(f"  Chunks created: {stats['chunks_created']}")
    print(f"  Total in DB:    {stats['total_chunks_in_db']}")
    print(f"  Errors:         {stats['errors']}")
    if stats["vaults"]:
        print(f"\n  Per vault:")
        for vname, vstats in stats["vaults"].items():
            print(f"    {vname}: {vstats['files']} files, {vstats['chunks']} chunks")
    print()


def cmd_update(provider, chroma_store, vaults):
    """Incremental update — only index changed files."""
    chunker = _make_chunker()
    indexer = VaultIndexer(
        vault_paths=vaults,
        provider=provider,
        chroma_store=chroma_store,
        chunker=chunker,
        hash_cache_path=Config.HASH_CACHE_PATH,
    )

    t0 = time.time()
    stats = indexer.index_update()
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f" Incremental Update Complete ({elapsed:.1f}s)")
    print(f"{'='*60}")
    print(f"  Provider:        {provider.name}")
    print(f"  Files changed:   {stats['files_changed']}")
    print(f"  Chunks created:  {stats['chunks_created']}")
    print(f"  Chunks removed:  {stats['chunks_removed']}")
    print(f"  Total in DB:     {stats['total_chunks_in_db']}")
    print(f"  Errors:          {stats['errors']}")
    if stats["vaults"]:
        any_changes = any(
            v.get("files_changed", 0) or v.get("removed", 0)
            for v in stats["vaults"].values()
        )
        if not any_changes:
            print(f"\n  No files changed — nothing to update.")
        else:
            print(f"\n  Per vault:")
            for vname, vstats in stats["vaults"].items():
                parts = []
                fc = vstats.get("files_changed", 0)
                if fc:
                    parts.append(f"{fc} changed")
                rm = vstats.get("removed", 0)
                if rm:
                    parts.append(f"{rm} removed")
                if parts:
                    print(f"    {vname}: {', '.join(parts)}")
    print()


def cmd_search(provider, chroma_store, query: str, args):
    """Search indexed vaults."""
    engine = SearchEngine(provider=provider, chroma_store=chroma_store)

    results = engine.search(
        query=query,
        n_results=args.n_results,
        vault=args.vault if args.vault != "all" else None,
    )

    print(f"\n{'='*60}")
    print(f" Search Results: \"{query}\"")
    print(f"{'='*60}")
    print(engine.format_results(results, show_text=True, max_text_chars=400))
    print(f"\n{len(results)} result(s) using {provider.name}")
    print()


def cmd_interactive_search(provider, chroma_store, args):
    """Interactive search loop."""
    engine = SearchEngine(provider=provider, chroma_store=chroma_store)
    vault_filter = args.vault if args.vault != "all" else None

    print(f"\nInteractive search mode (provider: {provider.name})")
    print("Type a query or 'quit'/'exit' to stop.\n")

    while True:
        try:
            query = input("search> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            break

        results = engine.search(
            query=query,
            n_results=args.n_results,
            vault=vault_filter,
        )
        print(engine.format_results(results, show_text=True, max_text_chars=400))
        print(f"{len(results)} result(s)\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Obsidian Vault Semantic Indexing and Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Actions (mutually exclusive, but we handle combinations)
    parser.add_argument(
        "--full", action="store_true", help="Full rebuild of all vaults"
    )
    parser.add_argument(
        "--update", action="store_true", help="Incremental update (only changed files)"
    )
    parser.add_argument(
        "--search",
        type=str,
        nargs="?",
        const="__interactive__",
        default=None,
        metavar="QUERY",
        help="Semantic search query. Use --search 'query' or --search alone for interactive mode",
    )

    # Options
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "openrouter"],
        default=None,
        help=f"Embedding provider (default: {Config.EMBEDDING_PROVIDER}). "
        "ollama=bge-m3 (local, 1024-dim), openrouter=text-embedding-3-large (cloud, 3072-dim)",
    )
    parser.add_argument(
        "--vault",
        type=str,
        default="all",
        help="Vault to search/index (default: all). Use vault folder name, e.g. 'MyVault'",
    )
    parser.add_argument(
        "--n-results",
        type=int,
        default=10,
        help="Number of search results (default: 10)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Load vaults
    vaults = Config.load_vaults()

    # Filter by vault if specified
    if args.vault != "all":
        if args.vault not in vaults:
            logger.error(
                "Unknown vault '%s'. Available: %s",
                args.vault,
                ", ".join(vaults.keys()),
            )
            sys.exit(1)
        vaults = {args.vault: vaults[args.vault]}

    # Validate that at least one vault exists
    existing_vaults = {n: p for n, p in vaults.items() if __import__("os").path.isdir(p)}
    if not existing_vaults:
        logger.error("No valid vault paths found. Checked: %s", vaults)
        sys.exit(1)
    if len(existing_vaults) < len(vaults):
        missing = set(vaults.keys()) - set(existing_vaults.keys())
        logger.warning("Skipping missing vaults: %s", missing)

    # Initialize provider
    try:
        provider = init_provider(args)
        logger.info("Using embedding provider: %s", provider.name)
    except RuntimeError as e:
        logger.error("%s", e)
        sys.exit(1)

    # Initialize ChromaDB — one collection per provider key so providers with
    # different dimensions never collide (e.g. bge-m3=1024, text-embedding-3-large=3072).
    collection_name = Config.collection_name(provider.key)
    chroma_store = ChromaStore(
        persist_directory=Config.CHROMA_PERSIST_DIR,
        collection_name=collection_name,
        embedding_dimension=provider.dimension,
    )
    logger.info(
        "ChromaDB ready at %s | collection=%s (%d-dim) | %d chunks",
        Config.CHROMA_PERSIST_DIR,
        collection_name,
        provider.dimension,
        chroma_store.count(),
    )

    # Dispatch
    if args.search:
        if args.search == "__interactive__":
            cmd_interactive_search(provider, chroma_store, args)
        else:
            cmd_search(provider, chroma_store, args.search, args)
    elif args.full:
        cmd_full(provider, chroma_store, existing_vaults)
    elif args.update:
        cmd_update(provider, chroma_store, existing_vaults)
    else:
        # Default: show summary
        count = chroma_store.count()
        print(f"\n{'='*60}")
        print(f" Obsidian Embeddings — Status")
        print(f"{'='*60}")
        print(f"  Provider:      {provider.name}")
        print(f"  ChromaDB:      {Config.CHROMA_PERSIST_DIR}")
        print(f"  Total chunks:  {count}")
        print(f"  Vaults:")
        for name, path in vaults.items():
            exists = "✓" if __import__("os").path.isdir(path) else "✗"
            print(f"    {exists} {name}: {path}")
        print(f"\n  No action specified. Use --full, --update, or --search.\n")
        parser.print_help()


if __name__ == "__main__":
    main()
