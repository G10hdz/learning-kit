#!/usr/bin/env python3
"""Read-only MCP bridge to the founder-guide REST API.

Exposes search/answer tools over stdio. Admin and ingestion endpoints are
intentionally not exposed to the model.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("FOUNDER_GUIDE_URL", "http://172.27.0.1:8080").rstrip("/")
TOKEN = os.environ.get("FOUNDER_GUIDE_TOKEN", "")
TIMEOUT = float(os.environ.get("FOUNDER_GUIDE_TIMEOUT", "20"))

mcp = FastMCP("founder-guide")


def _call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def _error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"founder-guide error: HTTP {exc.code} {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        return f"founder-guide unreachable at {BASE_URL}: {exc.reason}"
    return f"founder-guide request failed: {exc}"


def _citation(src: dict, id_key: str = "citationId") -> str:
    title = src.get("title") or src.get(id_key) or "source"
    url = src.get("url") or ""
    start = src.get("startSeconds")
    if isinstance(start, (int, float)) and url and "t=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}t={int(start)}"
    return f"{title} — {url}" if url else title


@mcp.tool()
def founder_guide_search(query: str, scope: str = "shared", limit: int = 8) -> str:
    """Search the founder-guide knowledge base (transcripts, books, research notes).

    Returns ranked excerpts with citations (title + timestamped source URL).
    Use this to ground advice in the recorded knowledge rather than guessing.
    """
    limit = max(1, min(limit, 50))
    qs = urllib.parse.urlencode({"q": query, "scope": scope, "limit": limit})
    try:
        data = _call("GET", f"/v1/search?{qs}")
    except Exception as exc:
        return _error(exc)
    items = data.get("items") or []
    if not items:
        return "No results in founder-guide for that query."
    return "\n\n".join(
        f"{i}. {item.get('text', '').strip()}\n   Source: {_citation(item.get('source') or {})}"
        for i, item in enumerate(items, 1)
    )


@mcp.tool()
def founder_guide_answer(question: str, scope: str = "shared", limit: int = 10) -> str:
    """Ask founder-guide a question; get a synthesized answer with citations.

    Prefer this for decision or 'what do our sources say about X' questions.
    Flags insufficient evidence instead of fabricating.
    """
    limit = max(1, min(limit, 50))
    try:
        data = _call(
            "POST",
            "/v1/answers",
            {"question": question, "scope": scope, "limit": limit},
        )
    except Exception as exc:
        return _error(exc)
    answer = (data.get("answer") or "").strip() or "(empty answer)"
    if data.get("insufficientEvidence"):
        answer += "\n\n[founder-guide reports insufficient evidence for this question]"
    citations = data.get("citations") or []
    if citations:
        answer += "\n\nCitations:\n" + "\n".join(
            f"- {_citation(c, 'sourceId')}" for c in citations
        )
    return answer


if __name__ == "__main__":
    mcp.run()
